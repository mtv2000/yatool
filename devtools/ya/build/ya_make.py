from __future__ import print_function
import collections
import copy
import glob
import logging
import os
import subprocess
import sys
import tempfile
import time
import six.moves.cPickle as cPickle

import six

import typing as tp  # noqa

import app_config
from test import const

import test.util.tools as test_tools

from exts import func
from exts.decompress import udopen
import exts.asyncthread as core_async
import exts.filelock
import exts.fs
import exts.hashing as hashing
import exts.http_client
import exts.os2
import exts.path2
import exts.timer
import exts.tmp
import exts.windows
import exts.yjson as json

from yalibrary.runner import patterns as ptrn
from yalibrary.runner import uid_store
from yalibrary.last_failed import last_failed
from yalibrary.runner import ring_store
from yalibrary.runner import result_store
from yalibrary import tools
from yalibrary.toolscache import (
    toolscache_version,
    get_task_stats,
    release_all_data,
    post_local_cache_report,
    tc_force_gc,
)
from yalibrary.yandex.distbuild import distbs_consts
from yalibrary.ya_helper.ya_utils import CacheKind

from build.reports import configure_error as ce
from build.reports import results_report
import build.reports.autocheck_report as ar
import build.reports.results_listener as pr

import core.config as core_config
import core.yarg
import core.error
import core.profiler as cp
import core.report
from core import stage_tracer

import test.common as test_common

import build.build_plan as bp
import build.build_result as br
import build.gen_plan as gp
import build.graph as lg
import build.makefile as mk
import build.owners as ow
import build.prefetch as pf
import build.stat.graph_metrics as st
import build.stat.statistics as bs
from build import build_facade, frepkage, test_results_console_printer
from build.reports import build_reports as build_report
from build.evlog.progress import ModulesFilesStatistic, PrintProgressListener, get_print_status_func, YmakeTimeStatistic

try:
    from yalibrary import build_graph_cache
except ImportError:
    build_graph_cache = None


CACHE_GENERATION = '2'

ARC_PREFIX = 'arcadia/'
ATD_PREFIX = 'arcadia_tests_data/'

logger = logging.getLogger(__name__)
stager = stage_tracer.get_tracer("ya_make")


class ConfigurationError(Exception):
    mute = True

    def __init__(self, msg=None):
        super(ConfigurationError, self).__init__(msg or 'Configure error (use -k to proceed)')


class EmptyProfilesListException(Exception):
    mute = True


def match_urls_and_outputs(urls, outputs):
    def norm(p):
        return os.path.normpath(p).replace('$(BUILD_ROOT)/', '')

    result = {}
    urls = set((norm(u), u) for u in urls)
    assert len(urls) == len(outputs), (urls, outputs)
    norm_outs = [(norm(o), o) for o in outputs]
    for norm_out, out in sorted(norm_outs, key=lambda oo: len(oo[1]), reverse=True):
        for norm_url, url in urls:
            if norm_url.endswith(norm_out):
                result[url] = out
                urls.remove((norm_url, url))
                break

    assert len(urls) == 0, urls
    return result


def remove_safe(p):
    try:
        exts.fs.remove_tree(p)
    except OSError as e:
        logger.debug('in remove_safe(): %s', e)


def normalize_by_dir(dirs, dir_):
    res = []

    for d in dirs:
        if exts.path2.path_startswith(d, dir_):
            res.append(dir_)

        else:
            res.append(d)

    return res


def get_print_listener(opts, display, printed=None):
    if printed is None:
        printed = set()

    def should_print(msg):
        if opts.be_verbose:
            return True

        if 'noauto' in msg:
            if msg.strip().endswith('.py'):
                return False

        return True

    def print_listener(ev):
        if ev['_typename'] == 'NEvent.TDisplayMessage':
            severity = ev['Type']
            sub = '[' + ev['Sub'] + ']' if ev['Sub'] else ''
            data = ev['Message']

            data = six.ensure_str(data)

            where = 'in [[imp]]{}[[rst]]'.format(ev['Where']) if 'Where' in ev else ''
            if len(where):
                where += ':{}:{}: '.format(ev['Row'], ev['Column']) if 'Row' in ev and 'Column' in ev else ': '
            platform = '{{{}}} '.format(ev['Platform']) if 'Platform' in ev else ''

            msg = '{}[[{}]]{}{}[[rst]]: {}{}'.format(platform, ev['Mod'], severity, sub, where, data)
            if msg not in printed and (opts.be_verbose or severity != 'Debug'):
                printed.add(msg)

                if should_print(msg):
                    display.emit_message(msg)

    return print_listener


def ymake_listener(evlog_writer):
    def listener(event):
        evlog_writer(event['_typename'], **event)

    return listener


class CompositeEventListener(object):
    def __init__(self, listeners=None):
        self._listeners = listeners if listeners is not None else []

    def append(self, listener):
        self._listeners.append(listener)

    def prepend(self, listener):
        self._listeners.insert(0, listener)

    def __call__(self, event):
        if self._is_dropped(event):
            return
        for listener in self._listeners:
            listener(event)
            if self._is_dropped(event):
                break

    @staticmethod
    def _is_dropped(event):
        return 'drop_event' in event and event['drop_event']


def compose_listeners(*listeners):
    return CompositeEventListener(listeners=listeners)


def _checkout(opts, display=None):
    if not getattr(opts, "checkout", False):
        return

    from yalibrary import checkout

    fetcher = checkout.VcsFetcher(opts.arc_root)

    from build import evlog

    fetcher.fetch_base_dirs(
        thin_checkout=opts.thin_checkout, extra_paths=opts.checkout_extra_paths, quiet=opts.checkout_quiet
    )
    fetcher.fetch_dirs(opts.rel_targets, quiet=opts.checkout_quiet)

    missing_dirs = set()
    root_dirs = set()

    opts2 = copy.deepcopy(opts)

    opts2.continue_on_fail = True
    opts2.debug_options += ['x']

    while True:
        events = []
        try:
            lg.build_graph_and_tests(opts2, check=False, ev_listener=events.append, display=display)
        except lg.GraphMalformedException:
            pass
        dirs, root_dirs = evlog.missing_dirs(events, root_dirs)

        if not opts.thin_checkout:
            # in the name of windows
            dirs = normalize_by_dir(dirs, 'contrib/java')

        dirs = [x if not x.startswith(ARC_PREFIX) else x[len(ARC_PREFIX) :] for x in dirs]
        add_arcadia_dirs, add_data_dirs = [], []
        for x in dirs:
            if x not in missing_dirs:
                if x.startswith(ATD_PREFIX):
                    add_data_dirs.append(x)
                else:
                    add_arcadia_dirs.append(x)
        missing_dirs.update(add_arcadia_dirs)
        missing_dirs.update(add_data_dirs)
        if add_arcadia_dirs:
            fetcher.fetch_dirs(add_arcadia_dirs, quiet=opts.checkout_quiet)
        if add_data_dirs:
            fetcher.fetch_dirs(
                [x[len(ATD_PREFIX) :] for x in add_data_dirs],
                quiet=opts.checkout_quiet,
                destination=opts.arcadia_tests_data_path,
                rel_root_path='../arcadia_tests_data',
            )
        if add_arcadia_dirs or add_data_dirs:
            continue
        break


def _build_graph_and_tests(opts, app_ctx, modules_files_stats, ymake_stats):
    # type: (tp.Any, tp.Any, tp.Any, YmakeTimeStatistic) -> tuple(tp.Any, tp.Any, tp.Any, tp.Any, tp.Any)
    display = getattr(app_ctx, 'display', None)
    _checkout(opts, display)

    prefetcher = pf.start_prefetch(opts) if opts.prefetch else None

    printed = set()
    errors = collections.defaultdict(set)

    def configure_messages_listener(event):
        if event['_typename'] == 'NEvent.TDisplayMessage' and event['Type'] == 'Error' and 'Where' in event:
            platform = '{{{}}}: '.format(event['Platform']) if 'Platform' in event else ''
            errors[event['Where']].add(
                ce.ConfigureError(platform + event['Message'].strip(), event.get('Row', 0), event.get('Column', 0))
            )
        elif event['_typename'] == 'NEvent.TLoopDetected' and event.get('LoopNodes'):
            nodes = []
            for item in event['LoopNodes']:
                nodes.append(item['Name'])

            message = 'Loop detected: ' + ' --> '.join(reversed(nodes))
            for item in event['LoopNodes']:
                if item['Type'] == 'Directory':
                    errors[item['Name']].add(ce.ConfigureError(message, 0, 0))

        logger.debug('Configure message {}'.format(event))

    ev_listener = CompositeEventListener(
        listeners=[
            PrintProgressListener(modules_files_stats),
            get_print_listener(opts, display, printed),
            ymake_stats.get_ymake_listener(),
            configure_messages_listener,
        ]
    )
    if getattr(app_ctx, 'evlog', None):
        ev_listener.append(ymake_listener(app_ctx.evlog.get_writer('ymake')))
    if prefetcher is not None:
        ev_listener.prepend(prefetcher.event_listener)

    try:
        graph, tests, stripped_tests, _, make_files = lg.build_graph_and_tests(
            opts, check=True, ev_listener=ev_listener, display=display
        )
    finally:
        if prefetcher is not None:
            prefetcher.stop()

    def fix_dir(s):
        if s.startswith('$S/'):
            s = s.replace('$S/', '').replace('/ya.make', '')
        elif s.startswith('$B/'):
            s = os.path.dirname(s).replace('$B/', '')
        return s

    errors = {fix_dir(k): sorted(list(v)) for k, v in six.iteritems(errors)}
    return graph, tests, stripped_tests, errors, make_files


def _advanced_lock_available(opts):
    return not exts.windows.on_win() and getattr(opts, 'new_store', False)


def make_lock(opts, garbage_dir, write_lock=False, non_blocking=False):
    exts.fs.ensure_dir(garbage_dir)
    lock_file = os.path.join(garbage_dir, '.lock')

    if _advanced_lock_available(opts):
        from exts.plocker import Lock, LOCK_EX, LOCK_NB, LOCK_SH

        timeout = 2 if non_blocking else 1000000000
        return Lock(lock_file, mode='w', timeout=timeout, flags=LOCK_EX | LOCK_NB if write_lock else LOCK_SH | LOCK_NB)

    return exts.filelock.FileLock(lock_file)


def _setup_content_uids(opts, enable):
    if not getattr(opts, 'force_content_uids', False):
        if getattr(opts, 'request_content_uids', False):
            if enable:
                logger.debug('content UIDs enabled by request')
                opts.force_content_uids = True
            else:
                logger.debug('content UIDs disabled: incompatible with cache version')
        else:
            logger.debug('content UIDs disabled by request')
    else:
        logger.debug('content UIDs forced')


def make_cache(opts, garbage_dir):
    if exts.windows.on_win():
        _setup_content_uids(opts, False)
        return uid_store.UidStore(os.path.join(garbage_dir, 'cache', CACHE_GENERATION))

    if getattr(opts, 'build_cache', False):
        from yalibrary.toolscache import ACCache, buildcache_enabled

        # garbage_dir is configured in yalibrary.toolscache
        if buildcache_enabled(opts):
            _setup_content_uids(opts, True)
            return ACCache(os.path.join(garbage_dir, 'cache', '7'))

    _setup_content_uids(opts, False)
    if getattr(opts, 'new_store', False) and getattr(opts, 'new_runner', False):
        from yalibrary.store import new_store

        # FIXME: This suspected to have some race condition in current content_uids implementation (see YMAKE-701)
        store = new_store.NewStore(os.path.join(garbage_dir, 'cache', '6'))
        return store
    else:
        return ring_store.RingStore(os.path.join(garbage_dir, 'cache', CACHE_GENERATION))


def init_bazel_remote_cache(opts):
    use_bazel_dist_cache = all(
        (
            getattr(opts, 'bazel_remote_store', False),
            not (getattr(opts, 'use_distbuild', False) and getattr(opts, 'bazel_readonly', False)),
        )
    )
    if use_bazel_dist_cache:
        from yalibrary.store.bazel_store import bazel_store

        base_uri = getattr(opts, 'bazel_remote_baseuri', None)
        if base_uri:
            password = getattr(opts, 'bazel_remote_password', None)
            password_file = getattr(opts, 'bazel_remote_password_file', None)
            if not password and password_file:
                logger.debug("Using '%s' file to obtain bazel remote password", password_file)
                with open(password_file) as afile:
                    password = afile.read()

            def fits_filter(node):
                # XXX Noda -> <dict>
                if not isinstance(node, dict):
                    node = node.args
                return is_dist_cache_suitable(node, None, opts)

            return bazel_store.BazelStore(
                base_uri=base_uri,
                username=getattr(opts, 'bazel_remote_username', None),
                password=password,
                readonly=getattr(opts, 'bazel_remote_readonly', True),
                max_connections=getattr(opts, 'dist_store_threads', 24),
                fits_filter=fits_filter,
            )


def init_yt_dist_cache(opts):
    try:
        import app_config

        yt_store_enabled = app_config.in_house
    except ImportError:
        yt_store_enabled = False

    use_dist_cache = all(
        (
            yt_store_enabled,
            getattr(opts, 'yt_store', False),
            not (getattr(opts, 'use_distbuild', False) and getattr(opts, 'yt_readonly', False)),
        )
    )
    if not use_dist_cache:
        return None
    token = opts.yt_token or opts.oauth_token
    if not token:
        try:
            from yalibrary import oauth

            token = oauth.get_token(core_config.get_user())
        except Exception as e:
            logger.warning("Failed to get YT token: %s", str(e))

    try:
        from yalibrary.store.yt_store import yt_store
    except ImportError as e:
        logger.warning("YT store is not available: %s", e)
        return None

    yt_store_class = yt_store.YndexerYtStore if opts.yt_replace_result_yt_upload_only else yt_store.YtStore
    return yt_store_class(
        opts.yt_proxy,
        opts.yt_dir,
        opts.yt_cache_filter,
        token=token,
        readonly=opts.yt_readonly,
        create_tables=opts.yt_create_tables,
        max_cache_size=opts.yt_max_cache_size,
        ttl=opts.yt_store_ttl,
    )


def make_dist_cache(dist_cache_future, opts, uids, heater_mode):
    if not uids:
        return None

    try:
        logger.debug("Waiting for dist cache setup")
        cache = dist_cache_future()
        if cache:
            logger.debug("Loading meta from dist cache")
            cache.load_meta(uids, heater_mode=heater_mode, refresh_on_read=opts.yt_store_refresh_on_read)

        logger.debug("Dist cache prepared")
        return cache
    except Exception as e:
        err = str(e)
        core.report.telemetry.report(
            core.report.ReportTypes.YT_CACHE_ERROR,
            {
                "error": "Can't use YT cache",
                "user": core_config.get_user(),
            },
        )
        logger.warning(
            'Can\'t use dist cache: %s... <Truncated. Complete message will be available in debug logs>', err[:100]
        )
        logger.debug('Can\'t use dist cache: %s', err)
        if opts.yt_store_exclusive or heater_mode:
            raise
        return None


def make_runner():
    from yalibrary.runner import runner3

    return runner3.run


def load_configure_errors(errors):
    loaded_errors = collections.defaultdict(list)

    if not errors:
        return loaded_errors
    else:
        for path, errorList in six.iteritems(errors):
            if errorList == 'OK':
                loaded_errors[path].append(ce.ConfigureError('OK', 0, 0))
                continue

            for error in errorList:
                if isinstance(error, list) and len(error) == 3:
                    loaded = ce.ConfigureError(error[0], error[1], error[2])
                else:
                    logger.debug('Suspicious configure error type: %s (error: %s)', str(type(error)), str(error))
                    loaded = ce.ConfigureError(str(error), 0, 0)
                loaded_errors[path].append(loaded)

        return loaded_errors


def configure_build_graph_cache_dir(app_ctx, opts):
    if opts.build_graph_cache_heater:
        return

    if build_graph_cache:
        build_graph_cache_resource_dir = build_graph_cache.BuildGraphCacheResourceDir(app_ctx, opts)

    try:
        logger.debug("Build graph cache processing started")
        if not build_graph_cache or not build_graph_cache_resource_dir.enabled():
            logger.debug("Build graph cache processing disabled")
            if not build_graph_cache:
                logger.debug('Build graph cache is not available in opensource')
                return

            if build_graph_cache.is_cache_provided(opts) and not opts.build_graph_cache_cl and not opts.distbuild_patch:
                logger.warning(
                    '--build-graph-cache-dir/--build-graph-cache-archive needs change list provided with --build-graph-cache-cl for improved ymake performance'
                )
                return

            opts.build_graph_cache_cl = (
                build_graph_cache.prepare_change_list(opts) if build_graph_cache.is_cache_provided(opts) else None
            )
            return

        # Validate opts.build_graph_cache_resource.
        logger.debug("Getting build graph cache resource id")
        opts.build_graph_cache_resource = build_graph_cache_resource_dir.resource_id

        if build_graph_cache_resource_dir.safe_ymake_cache:
            logger.debug(
                'Safe caches set for resource {}: {}'.format(
                    build_graph_cache_resource_dir.resource_id, build_graph_cache_resource_dir.safe_ymake_cache
                )
            )
            if opts.build_graph_use_ymake_cache_params and 'normal' in opts.build_graph_use_ymake_cache_params:
                logger.debug(
                    'build_graph_use_ymake_cache_params before downgrade to safe caches: {}'.format(
                        opts.build_graph_use_ymake_cache_params
                    )
                )
                opts.build_graph_use_ymake_cache_params['normal'] = CacheKind.get_ymake_option(
                    build_graph_cache_resource_dir.safe_ymake_cache
                )
                opts.build_graph_use_ymake_cache_params_str = json.dumps(opts.build_graph_use_ymake_cache_params)
                logger.debug(
                    'build_graph_use_ymake_cache_params after downgrade to safe caches: {}'.format(
                        opts.build_graph_use_ymake_cache_params
                    )
                )

        download = not (opts.make_context_on_distbuild or opts.make_context_on_distbuild_only or opts.make_context_only)
        if download:
            logger.debug("Downloading build graph cache resource")
            opts.build_graph_cache_archive = build_graph_cache_resource_dir.download_build_graph_cache()

        logger.debug("Getting change list for build graph cache")
        opts.build_graph_cache_cl = build_graph_cache_resource_dir.merge_change_lists(opts)
        logger.debug("Build graph cache enabled")
    except Exception as e:
        build_graph_cache.reset_build_graph_cache(opts)
        logger.exception("(ya_make) Build graph cache disabled %s", e)


def get_suites_exit_code(suites, test_fail_exit_code=const.TestRunExitCode.Failed):
    statuses = set([suite.get_status() for suite in suites if not suite.is_skipped()])
    if not statuses or statuses == {const.Status.GOOD}:
        exit_code = 0
    elif const.Status.INTERNAL in statuses:
        exit_code = const.TestRunExitCode.InfrastructureError
    else:
        exit_code = int(test_fail_exit_code)
    return exit_code


# TODO: Merge to Context
class BuildContext(object):
    @classmethod
    def load(cls, params, app_ctx, data):
        kwargs = {'encoding': 'utf-8'} if six.PY3 else {}
        builder = YaMake(
            params,
            app_ctx,
            graph=data.get('graph'),
            tests=[
                cPickle.loads(six.ensure_binary(pickled_test, encoding='latin-1'), **kwargs)
                for pickled_test in data['tests'].values()
            ],
            stripped_tests=[
                cPickle.loads(six.ensure_binary(pickled_test, encoding='latin-1'), **kwargs)
                for pickled_test in data.get('stripped_tests', {}).values()
            ],
            configure_errors=data['configure_errors'],
            make_files=data['make_files'],
            lite_graph=data['lite_graph'],
        )
        return BuildContext(builder, owners=data['owners'])

    def __init__(self, builder, owners=None, ctx=None):
        self.builder = builder
        self.ctx = ctx
        self.owners = owners or builder.get_owners()

    def save(self):
        ctx = self.ctx or self.builder.ctx
        return {
            'configure_errors': ctx.configure_errors,
            'tests': {test.uid: six.ensure_str(cPickle.dumps(test), encoding='latin-1') for test in ctx.tests},
            'stripped_tests': {
                test.uid: six.ensure_str(cPickle.dumps(test), encoding='latin-1') for test in ctx.stripped_tests
            },
            'make_files': ctx.make_files,
            'owners': self.owners,
            'graph': ctx.graph,
            'lite_graph': ctx.lite_graph,
        }


def is_local_build_with_tests(opts):
    return (
        not (os.environ.get('AUTOCHECK', False) or hasattr(opts, 'flags') and opts.flags.get('AUTOCHECK', False))
        and opts.run_tests
    )


def need_cache_test_statuses(opts):
    if opts.cache_test_statuses is not None:
        return opts.cache_test_statuses
    return is_local_build_with_tests(opts)


# XXX see YA-1354
def replace_dist_cache_results(graph, opts, dist_cache, app_ctx):
    if not dist_cache:
        return []

    orig_result = set(graph['result'])

    def suitable(node):
        return is_dist_cache_suitable(node, orig_result, opts)

    def check(node):
        app_ctx.state.check_cancel_state()
        uid = node['uid']
        if dist_cache.fits(node) and suitable(node) and not dist_cache.has(uid):
            return uid
        return None

    result = set(core_async.par_map(check, graph['graph'], opts.dist_store_threads))
    result.discard(None)
    return list(sorted(result))


def is_target_binary(node):
    is_binary = node.get('target_properties', {}).get('module_type', None) == 'bin'
    return is_binary and not node.get('host_platform')


def is_dist_cache_suitable(node, result, opts):
    if opts.dist_cache_evict_binaries and is_target_binary(node):
        return False

    module_tag = node.get('target_properties', {}).get('module_tag', None)
    if module_tag in ('jar_runable', 'jar_runnable', 'jar_testable'):
        return False

    if 'module_type' in node.get('target_properties', {}):
        return True

    # If all checks are passed - all result nodes are suitable
    if result is not None:
        return node['uid'] in result
    # If result node are not specified -
    return True


# XXX see YA-1354
def replace_yt_results(graph, opts, dist_cache):
    assert 'result' in graph

    if not dist_cache:
        return [], []

    new_results = []
    cached_results = []

    if not opts.yt_cache_filter:
        original_results = set(graph.get('result', []))
        network_limited_nodes = set()

        def network_limited(node):
            return node.get("requirements", {}).get("network") == "full"

        def suitable(node):
            if opts.yt_replace_result_yt_upload_only:
                return any(out.endswith('.ydx.pb2.yt') for out in node.get('outputs', []))
            if opts.yt_replace_result_add_objects and any(out.endswith('.o') for out in node.get('outputs', [])):
                return True

            return is_dist_cache_suitable(node, original_results, opts)

        first_pass = []
        for node in graph['graph']:
            uid = node.get('uid')

            if network_limited(node):
                network_limited_nodes.add(uid)

            if dist_cache.fits(node) and suitable(node):
                # (node, new_result)
                first_pass.append((node, not dist_cache.has(node.get('uid'))))

        # Another pass to filter out network intensive nodes.
        for node, new_result in first_pass:
            uid = node.get('uid')
            if not opts.yt_replace_result_yt_upload_only:
                if uid in network_limited_nodes:
                    continue
                deps = node.get('deps', [])
                # It is dependence on single fetch_from-like node.
                if len(deps) == 1 and deps[0] in network_limited_nodes:
                    continue

            if new_result:
                new_results.append(uid)
            else:
                cached_results.append(uid)
    else:
        for node in graph.get('graph'):
            uid = node.get('uid')
            if dist_cache.fits(node) and not dist_cache.has(uid):
                new_results.append(uid)

    return new_results, cached_results


class Context(object):
    def __init__(
        self,
        opts,
        app_ctx,
        graph=None,
        tests=None,
        stripped_tests=None,
        configure_errors=None,
        make_files=None,
        lite_graph=None,
    ):
        timer = exts.timer.Timer('context_creation')
        context_creation_stage = stager.start('context_creation')

        self.stage_times = {}

        self.opts = opts
        self.cache_test_statuses = need_cache_test_statuses(opts)

        def notify_locked():
            logger.info('Waiting for other build process to finish...')

        self.clear_cache_tray(opts)

        self.local_runner_ready = core_async.ProperEvent()

        self._lock = make_lock(opts, self.garbage_dir)

        self.clear_garbage(opts)

        other_build_notifier = core_async.CancellableTimer(notify_locked, 1.0)
        other_build_notifier.start(cancel_on=lambda: self.lock())

        self.threads = self.opts.build_threads

        self.create_output = self.opts.output_root is not None
        self.create_symlinks = getattr(self.opts, 'create_symlinks', True) and not exts.windows.on_win()

        def get_suppression_conf():
            suppress_outputs = getattr(self.opts, 'suppress_outputs', [])
            default_suppress_outputs = getattr(self.opts, 'default_suppress_outputs', [])
            add_result = getattr(self.opts, 'add_result', [])
            # '.a' in suppress_outputs overrides '.specific.a' in add_result
            add_result = [i for i in add_result if not any([i.endswith(x) for x in suppress_outputs])]
            # '.a' in add_result overrides '.specific.a' in default_suppress_outputs
            default_suppress_outputs = [
                i for i in default_suppress_outputs if not any([i.endswith(x) for x in add_result])
            ]

            return {
                'add_result': add_result,
                'suppress_outputs': suppress_outputs,
                'default_suppress_outputs': default_suppress_outputs,
            }

        self.suppress_outputs_conf = get_suppression_conf()

        self.output_replacements = [(opts.oauth_token, "<YA-TOKEN>")] if opts.oauth_token else []

        if getattr(opts, 'bazel_remote_store', False):
            dist_cache_future = core_async.future(lambda: init_bazel_remote_cache(opts))
        else:
            dist_cache_future = core_async.future(lambda: init_yt_dist_cache(opts))

        display = getattr(app_ctx, 'display', None)
        print_status = get_print_status_func(opts, display, logger)

        self.modules_files_stats = ModulesFilesStatistic(
            stream=print_status,
            is_rewritable=opts.output_style == 'ninja',
        )

        self.ymake_stats = YmakeTimeStatistic()

        self.lite_graph = None
        if (graph is not None or opts.use_lite_graph) and tests is not None:
            self.graph = graph
            self.tests = tests
            self.stripped_tests = []
            if stripped_tests is not None:
                self.stripped_tests = stripped_tests
            self.configure_errors = load_configure_errors(configure_errors)
            self.make_files = make_files or []
        elif opts.custom_json is not None and opts.custom_json:
            with udopen(opts.custom_json) as custom_json_file:
                self.graph = json.load(custom_json_file)
                lg.finalize_graph(self.graph, opts)
            self.tests = []
            self.stripped_tests = []
            self.configure_errors = {}
            self.make_files = []
        else:
            (
                self.graph,
                self.tests,
                self.stripped_tests,
                self.configure_errors,
                self.make_files,
            ) = _build_graph_and_tests(self.opts, app_ctx, self.modules_files_stats, self.ymake_stats)
            timer.show_step("graph_and_tests finished")

            if self.configure_errors and not opts.continue_on_fail:
                raise ConfigurationError()

        if self.graph is not None:
            self.graph['conf']['keepon'] = opts.continue_on_fail
            self.graph['conf'].update(gp.gen_description())
            if self.opts.default_node_requirements:
                self.graph['conf']['default_node_requirements'] = self.opts.default_node_requirements
            if self.opts.use_distbuild:
                if self.opts.distbuild_cluster:
                    self.graph['cluster'] = self.opts.distbuild_cluster
                if self.opts.coordinators_filter:
                    self.graph['conf']['coordinator'] = self.opts.coordinators_filter
                if self.opts.distbuild_pool:
                    self.graph['conf']['pool'] = self.opts.distbuild_pool

        nodes_map = {}
        for node in self.graph['graph'] if self.graph is not None else lite_graph['graph']:
            nodes_map[node['uid']] = node

        print_status("Configuring local and dist store caches")
        self.dist_cache = make_dist_cache(
            dist_cache_future, self.opts, nodes_map.keys(), heater_mode=not self.opts.yt_store_wt
        )
        self.cache = make_cache(self.opts, self.garbage_dir)

        print_status("Configuration done. Preparing for execution")

        sandbox_run_test_uids = set(self.get_context().get('sandbox_run_test_result_uids', []))
        logger.debug("sandbox_run_test_uids: %s", sandbox_run_test_uids)

        # XXX see YA-1354
        if opts.bazel_remote_store and (not opts.bazel_remote_readonly or opts.dist_cache_evict_cached):
            self.graph['result'] = replace_dist_cache_results(self.graph, opts, self.dist_cache, app_ctx)
            logger.debug("Strip graph due bazel_remote_store mode")
            self.graph = lg.strip_graph(self.graph)
            results = set(self.graph['result'])
            self.tests = [x for x in self.tests if x.uid in results]
        # XXX see YA-1354
        elif (
            not opts.use_lite_graph and (opts.yt_replace_result or opts.dist_cache_evict_cached) and not opts.add_result
        ):
            new_results, cached_results = replace_yt_results(self.graph, opts, self.dist_cache)
            self.graph['result'] = new_results
            logger.debug("Strip graph due yt_replace_result mode")
            self.graph = lg.strip_graph(self.graph)
            self.yt_cached_results = cached_results
            self.yt_not_cached_results = new_results
            results = set(self.graph['result'])
            self.tests = [x for x in self.tests if x.uid in results]

        elif opts.frepkage_target_uid:
            assert opts.frepkage_target_uid in graph['result'], (opts.frepkage_target_uid, graph['result'])
            logger.debug("Strip graph using %s uid as single result", opts.frepkage_target_uid)
            self.graph = lg.strip_graph(self.graph, result=[opts.frepkage_target_uid])
            self.tests = [x for x in self.tests if x.uid == opts.frepkage_target_uid]
            assert self.tests

        elif sandbox_run_test_uids:
            # XXX This is a place for further enhancement.
            # Prerequisites:
            #  - support all vcs
            #  - support branches
            #  - we can't get the graph without patch (to minimize uploading changes)
            #  - should take into account vcs untracked changes which might affect on test
            #  - local repository state might be heterogeneous (intentionally or not) - some parts of the repo might have different revisions, etc
            #  - can't apply patch over arcadia in the Sandbox task without information what inputs were removed or renamed
            #  - arbitrary build configurations specified by user
            # Current implementation pros:
            #  - all prerequisites are taken in to account
            #  - frepkage is fully hermetic and sandbox task doesn't need to setup arcadia repo - frepakge contains all required inputs
            #  - yt cache and local cache are reused
            #  - works in development mode with external inputs in graph (trunk ya-bin, --ymake-bin PATH, --test-tool-bin PATH)
            # Cons:
            #  - repkage contains all inputs from the graph, what can be excessive if there a lot of tests without ya:force_sandbox tag in the graph
            #    Their input data will also be uploaded, but will not be used.
            #    # TODO
            #      ymake/ya-bin should set proper inputs to the nodes which could be stripped.
            #      right now some nodes have not fully qualified inputs - this problem is masked and overlapped by the graph's 'inputs' section
            #  - doesn't support semidist mode (build arts on distbuild, run tests locally)
            #  - extremely huge input is a bottleneck
            # Notes:
            #  - currently doesn't support ATD (it's quite easy to fix, but we want people to use Sandbox instead of ATD)

            if self.opts.use_distbuild:
                raise core.yarg.FlagNotSupportedException(
                    "--run-tagged-tests-on-sandbox option doesn't support --dist mode"
                )

            if self.threads or self.opts.force_create_frepkage:
                print_status('Preparing frozen repository package')

                def get_sandbox_graph(graph):
                    graph = lg.strip_graph(graph, result=sandbox_run_test_uids)
                    # strip_graph() returns graph's shallow copy - deepcopy 'conf' section to save original one
                    graph['conf'] = copy.deepcopy(graph['conf'])
                    del graph['conf']['context']['sandbox_run_test_result_uids']
                    return graph

                frepkage_file = frepkage.create_frepkage(
                    build_context=BuildContext(builder=None, owners={'dummy': None}, ctx=self).save(),
                    graph=get_sandbox_graph(self.graph),
                    arc_root=self.opts.arc_root,
                )

                if self.opts.force_create_frepkage:
                    if os.path.exists(self.opts.force_create_frepkage):
                        os.unlink(self.opts.force_create_frepkage)
                    # Copy only valid and fully generated frepkage
                    exts.fs.hardlink_or_copy(frepkage_file, self.opts.force_create_frepkage)
            else:
                # Don't waste time preparing frepkage if -j0 is requested
                frepkage_file = 'frepkage_was_not_generated_due_-j0'

            from test import test_node

            # All tests have same global resources
            test_global_resources = self.tests[0].global_resources

            # Move frepkage uploading to the separate node in the graph to avoid a bottleneck
            upload_node, upload_res_info_filename = test_node.create_upload_frepkage_node(
                frepkage_file, test_global_resources, self.opts
            )
            self.graph['graph'].append(upload_node)
            # Create node to populate token to the vault which will be used in the task to access YT build cache
            # to speed up Sandbox task created by sandbox_run_test node
            populate_node = test_node.create_populate_token_to_sandbox_vault_node(test_global_resources, self.opts)
            self.graph['graph'].append(populate_node)

            # Replace ya:force_sandbox tagged result test nodes with sandbox_run_test node
            test_map = {x.uid: x for x in self.tests}
            for uid in sandbox_run_test_uids:
                node = nodes_map[uid]
                newnode = test_node.create_sandbox_run_test_node(
                    node,
                    test_map[uid],
                    nodes_map,
                    frepkage_res_info=upload_res_info_filename,
                    deps=[upload_node['uid'], populate_node['uid']],
                    opts=self.opts,
                )
                node.clear()
                node.update(newnode)

            # Strip dangling test nodes (such can be appeared if FORK_*TEST or --tests-retries were specified)
            self.graph = lg.strip_graph(self.graph)

            timer.show_step("sandbox_run_test_processing finished")

        # We assume that graph won't be modified after this point. Lite graph should be same as full one -- but lite!

        if lite_graph is not None:
            self.lite_graph = lite_graph
        else:
            self.lite_graph = lg.build_lite_graph(self.graph)

        self.mergers = [
            test_common.TestsMerger(n) for n in self.lite_graph['graph'] if node.get('node-type', '') == 'merger'
        ]

        if not opts.use_lite_graph:
            if app_config.in_house:
                import yalibrary.diagnostics as diag

                if diag.is_active():
                    diag.save('ya-make-full-graph', graph=json.dumps(self.graph, sort_keys=True, indent=4, default=str))
                    timer.show_step("full graph is dumped")

            if opts.show_command:
                self.threads = 0

                for flt in self.opts.show_command:
                    for node, full_match in lg.filter_nodes_by_output(self.graph, flt, warn=True):
                        print(json.dumps(node, sort_keys=True, indent=4, separators=(',', ': ')))
                timer.show_step("show_command finished")

            if opts.generate_makefile:
                makefile_generator = mk.MakefileGenerator()
                makefile_generator.gen_makefile(self.graph)
                timer.show_step("generate_makefile finished")

        if opts.dump_graph:
            if opts.use_lite_graph:
                graph_to_dump = self.lite_graph
                logger.warning("Full graph is not downloaded with option -use-lite-graph, dumping lite graph.")
            else:
                graph_to_dump = self.graph

            if opts.dump_graph_file:
                with open(opts.dump_graph_file, 'w') as gf:
                    json.dump(graph_to_dump, gf, sort_keys=True, indent=4, default=str)
            else:
                stdout = opts.stdout or sys.stdout
                json.dump(graph_to_dump, stdout, sort_keys=True, indent=4, default=str)
                stdout.flush()
            timer.show_step("dump_graph finished")

        self.runner = make_runner()

        if opts.cache_stat:
            self.cache.analyze(app_ctx.display)
            timer.show_step("cache_stat finished")

        self.output_result = result_store.ResultStore(self.output_dir) if self.create_output else None
        self.symlink_result = (
            result_store.SymlinkResultStore(self.symres_dir, getattr(self.opts, 'symlink_root', None) or self.src_dir)
            if self.create_symlinks
            else None
        )

        # XXX: Legacy (DEVTOOLS-1128)
        self.install_result = result_store.LegacyInstallResultStore(opts.install_dir) if opts.install_dir else None
        self.bin_result = (
            result_store.LegacyInstallResultStore(opts.generate_bin_dir) if opts.generate_bin_dir else None
        )
        self.lib_result = (
            result_store.LegacyInstallResultStore(opts.generate_lib_dir) if opts.generate_lib_dir else None
        )

        # XXX: Legacy (DEVTOOLS-1128) + build_root_set cleanup
        if (
            opts.run_tests <= 0
            and self.threads > 0
            and not opts.keep_temps
            and not self.output_result
            and not self.symlink_result
            and not self.install_result
            and not self.bin_result
            and not self.lib_result
        ):
            logger.warning(
                'Persistent storage for results is not specified. '
                + 'Remove --no-src-links option (*nix systems) and/or use -o/--output option, see details in help.'
            )

        context_creation_stage.finish()
        timer.show_step("context_creation finished")
        self.stage_times['context_creation'] = timer.full_duration()

    def get_context(self):
        return self.graph.get('conf', {}).get('context', {})

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        self._lock.release()

    def clear_cache_tray(self, opts):
        if _advanced_lock_available(opts):
            from exts.plocker import LockException

            try:
                with make_lock(opts, self.garbage_dir, write_lock=True, non_blocking=True):
                    self.cache = make_cache(self.opts, self.garbage_dir)
                    if hasattr(self.cache, 'clear_tray'):
                        self.cache.clear_tray()
            except LockException:
                pass

    def clear_garbage(self, opts):
        if not self.opts.do_clear:
            return
        # Do not remove lock file while locked
        assert self._lock
        with make_lock(opts, self.garbage_dir, write_lock=True):
            for filename in os.listdir(self.garbage_dir):
                if filename == self.lock_name:
                    continue
                exts.fs.remove_tree_safe(os.path.join(self.garbage_dir, filename))

    @property
    def abs_targets(self):
        return self.opts.abs_targets or [os.getcwd()]

    @property
    def garbage_dir(self):
        return self.opts.bld_dir

    @property
    def conf_dir(self):
        return os.path.join(self.garbage_dir, 'conf')

    @property
    def src_dir(self):
        return self.opts.arc_root

    @property
    def output_dir(self):
        return self.opts.output_root

    @property
    def symres_dir(self):
        return os.path.join(self.garbage_dir, 'symres')

    @property
    def res_dir(self):
        return core_config.tool_root(toolscache_version(self.opts))

    @property
    def lock_name(self):
        return '.lock'

    @property
    def lock_file(self):
        return os.path.join(self.garbage_dir, self.lock_name)


def extension(f):
    p = f.rfind('.')

    if p > 0:
        return f[p + 1 :]


def get_deps(targets, graph, build_result, dest_dir):
    if len(targets) > 1:
        logger.warning('Don\'t know which deps to dump. Candidates are %s', ', '.join(targets))
        return

    import jbuild.gen.base as base
    import jbuild.gen.actions.funcs as funcs

    result = frozenset(graph['result'])
    target = targets[0]

    for node in graph['graph']:
        if 'get-deps' in node.get('java_tags', []) and node['uid'] in result:
            assert node['uid'] in build_result.ok_nodes

            for out, res in zip(node['outputs'], build_result.ok_nodes[node['uid']]):
                this_target = base.relativize(os.path.dirname(os.path.dirname(out)))

                if target is None:
                    target = this_target

                elif this_target != target:
                    continue

                if 'artifact' in res:
                    jar_with_deps = res['artifact']

                elif 'symlink' in res:
                    jar_with_deps = res['symlink']

                else:
                    raise Exception('Build result for {} is invalid: {}'.format(out, str(res)))

                unpack_to = os.path.join(dest_dir, os.path.basename(os.path.dirname(jar_with_deps)))

                exts.fs.ensure_removed(unpack_to)
                exts.fs.create_dirs(unpack_to)
                funcs.jarx(jar_with_deps, unpack_to)()

    if target is not None:
        logger.info('Successfully dumped deps of %s: %s', target, dest_dir)


class YaMake(object):
    def __init__(
        self,
        opts,
        app_ctx,
        graph=None,
        tests=None,
        stripped_tests=None,
        configure_errors=None,
        make_files=None,
        lite_graph=None,
    ):
        self.opts = opts
        if getattr(opts, 'pgo_user_path', None):
            setattr(opts, 'pgo_path', merge_pgo_profiles(opts.pgo_user_path))
        self.app_ctx = app_ctx
        self._owners = None
        self._make_files = None
        self.raw_build_result = None
        self.build_root = None
        self.misc_build_info_dir = None
        self.arc_root = None
        self._setup(opts)
        self._validate_opts()
        self.ctx = Context(
            self.opts,
            app_ctx=app_ctx,
            graph=graph,
            tests=tests,
            stripped_tests=stripped_tests,
            configure_errors=configure_errors,
            make_files=make_files,
            lite_graph=lite_graph,
        )
        self._post_clean_setup(opts)
        self.build_result = br.BuildResult({}, {}, {})
        self.exit_code = 0
        self._build_results_listener = None
        self._output_root = None
        self._report = None
        self._reports_generator = None
        self._slot_time_listener = None

    def _setup(self, opts):
        self.opts = opts
        self.arc_root = opts.arc_root
        if not os.path.isabs(self.opts.arcadia_tests_data_path):
            self.opts.arcadia_tests_data_path = os.path.join(
                os.path.dirname(self.arc_root), self.opts.arcadia_tests_data_path
            )
        self._setup_environment()

    def _post_clean_setup(self, opts):
        self.misc_build_info_dir = getattr(opts, 'misc_build_info_dir', None) or tempfile.mkdtemp(
            prefix='ya-misc-build-info-dir'
        )
        exts.fs.create_dirs(self.misc_build_info_dir)

    def _setup_build_root(self, build_root):
        assert build_root, "Expected not empty build_root value"
        self.build_root = os.path.abspath(build_root)
        exts.fs.create_dirs(self.build_root)

    def _generate_report(self):
        logger.debug("Generating results report")
        build_report.generate_results_report(self)
        build_report.generate_empty_tests_result_report(self)

    def _dump_json(self, filename, content):
        with open(os.path.join(self.misc_build_info_dir, filename), 'w') as fp:
            json.dump(content, fp=fp, indent=4, sort_keys=True)

    def get_owners(self):
        if self._owners is None:
            owners = {}
            for entry in self.ctx.make_files:
                if 'OWNERS' in entry and 'PATH' in entry:
                    logins, groups = ow.make_logins_and_groups(entry['OWNERS'].split())
                    path = entry['PATH']
                    if path == '$S' or path.startswith('$S/'):
                        path = path[3:]
                    ow.add_owner(owners, path, logins, groups)
            self._owners = owners
        return self._owners

    @func.lazy_property
    def expected_build_targets(self):
        gen_build_targets_result = build_facade.gen_build_targets(
            build_root=self.opts.custom_build_directory,
            build_type=self.opts.build_type,
            build_targets=self.opts.abs_targets,
            debug_options=self.opts.debug_options,
            flags=self.opts.flags,
            ymake_bin=self.opts.ymake_bin,
        )
        if gen_build_targets_result.exit_code != 0:
            cp.profile_value('gen_build_targets_exit_code', gen_build_targets_result.exit_code)
            raise ConfigurationError(
                'Unable to get build targets names. Ymake says {0}'.format(gen_build_targets_result.stderr.strip())
            )

        return gen_build_targets_result.stdout.split()

    def get_make_files(self):
        if self._make_files is None:
            make_files = set()
            for entry in self.ctx.make_files:
                if 'PATH' in entry:
                    make_files.add(entry['PATH'].replace('$S/', ''))
            self._make_files = make_files
        return self._make_files

    def add_owner(self, path, logins, groups):
        ow.add_owner(self.get_owners(), path, logins, groups)

    def _setup_compact_for_gc(self):
        if not self.opts.strip_cache:
            return
        if not hasattr(self.ctx.cache, 'compact'):
            return

        if hasattr(self.ctx.cache, 'set_max_age'):
            self.ctx.cache.set_max_age(time.time())
        else:
            setattr(self.ctx.opts, 'new_store_ttl', 0)
            setattr(self.ctx.opts, 'cache_size', 0)

    def _strip_cache(self, threads):
        if not self.opts.strip_cache:
            return

        if hasattr(self.ctx.cache, 'compact'):
            if threads == 0:
                for node in self.ctx.lite_graph.get('graph', []):
                    self.ctx.cache.has(node['uid'])  # touch uid

                self.ctx.cache.compact(
                    getattr(self.ctx.opts, 'new_store_ttl'), getattr(self.ctx.opts, 'cache_size'), self.app_ctx.state
                )
        else:
            nodes = [node['uid'] for node in self.ctx.lite_graph.get('graph', [])]
            self.ctx.cache.strip(lambda info: info.uid in nodes)

        tc_force_gc(getattr(self.ctx.opts, 'cache_size'))

    def _setup_environment(self):
        os.environ['PORT_SYNC_PATH'] = os.path.join(self.opts.bld_dir, 'port_sync_dir')
        if (
            getattr(self.opts, "multiplex_ssh", False)
            and getattr(self.opts, "checkout", False)
            and not exts.windows.on_win()
        ):
            # https://stackoverflow.com/questions/34829600/why-is-the-maximal-path-length-allowed-for-unix-sockets-on-linux-108
            dirname = None
            candidates = [lambda: self.opts.bld_dir, lambda: tempfile.mkdtemp(prefix='yatmp')]
            for get_name in candidates:
                name = get_name()
                if len(name) < 70:
                    dirname = name
                    break
            if dirname:
                control_path = os.path.join(dirname, 'ymux_%p_%r')
                logger.debug(
                    "SSH multiplexing is enabled: control path: %s (%s)",
                    control_path,
                    os.path.exists(os.path.dirname(control_path)),
                )
                multiplex_opts = '-o ControlMaster=auto -o ControlPersist=3s -o ControlPath={}'.format(control_path)

                svn_ssh = os.environ.get('SVN_SSH')
                if not svn_ssh:
                    if not self.arc_root:
                        logger.debug("SSH multiplexing is disabled: no arcadia root specified")
                        return

                    from six.moves.urllib.parse import urlparse
                    import yalibrary.svn

                    svn_env = os.environ.copy()
                    svn_env['LC_ALL'] = 'C'
                    with exts.tmp.environment(svn_env):
                        try:
                            root_info = yalibrary.svn.svn_info(self.arc_root)
                        except yalibrary.svn.SvnRuntimeError as e:
                            if "is not a working copy" in e.stderr:
                                logger.debug(
                                    "SSH multiplexing is disabled: %s is not an svn working copy", self.arc_root
                                )
                                return
                            raise
                    svn_ssh = urlparse(root_info['url']).scheme.split('+')[-1]

                os.environ['SVN_SSH'] = "{} {}".format(svn_ssh, multiplex_opts)
                logger.debug("SVN_SSH=%s", os.environ['SVN_SSH'])
            else:
                logger.debug(
                    "SSH multiplexing is disabled: because none of the candidates meets the requirements (%s)",
                    candidates,
                )

    def _setup_repo_state(self):
        suites = [t for t in self.ctx.tests if not t.is_skipped()]
        source_root = self.ctx.src_dir
        for s in suites:
            test_project_path = getattr(s, "project_path", None)
            if test_project_path is None:
                continue
            test_results = os.path.join(source_root, test_project_path, "test-results")
            if os.path.islink(test_results):
                logger.debug("test-results link found: %s", test_results)
                os.unlink(test_results)

    def _setup_reports(self):
        self._build_results_listener = pr.CompositeResultsListener([])
        test_results_path = self._get_results_root()
        test_node_listener = pr.TestNodeListener(self.ctx.tests, test_results_path, None)
        if not self.opts.remove_result_node:
            self._build_results_listener.add(pr.TestResultsListener(self.ctx.lite_graph, self.app_ctx.display))

        if self.opts.dump_failed_node_info_to_evlog:
            self._build_results_listener.add(pr.FailedNodeListener(self.app_ctx.evlog))

        if all(
            [
                self.opts.json_line_report_file is None,
                self.opts.build_results_report_file is None,
                self.opts.streaming_report_id is None
                or (self.opts.streaming_report_url is None and not self.opts.report_to_ci),
            ]
        ):
            if self.opts.print_test_console_report:
                self._build_results_listener.add(test_node_listener)
            return

        results_dir = self.opts.misc_build_info_dir or self.opts.testenv_report_dir or tempfile.mkdtemp()
        self._output_root = self.opts.output_root or tempfile.mkdtemp()

        tests = (
            [t for t in self.ctx.tests if t.is_skipped()] if self.opts.report_skipped_suites_only else self.ctx.tests
        )
        self._report = results_report.StoredReport()
        report_list = [self._report]
        if self.opts.streaming_report_url or self.opts.report_to_ci:
            # streaming_client is not available in OSS version of the ya
            from yalibrary import streaming_client as sc

            if self.opts.report_to_ci:
                adapter = sc.StreamingCIAdapter(
                    self.opts.ci_logbroker_token,
                    self.opts.ci_topic,
                    self.opts.ci_source_id,
                    self.opts.ci_check_id,
                    self.opts.ci_check_type,
                    self.opts.ci_iteration_number,
                    self.opts.stream_partition,
                    self.opts.ci_task_id_string,
                    self.opts.streaming_task_id,
                    self.opts.ci_logbroker_partition_group,
                    use_ydb_topic_client=self.opts.ci_use_ydb_topic_client,
                )
            else:
                adapter = sc.StreamingHTTPAdapter(
                    self.opts.streaming_report_url,
                    self.opts.streaming_report_id,
                    self.opts.stream_partition,
                    self.opts.streaming_task_id,
                )
            report_list.append(
                results_report.AggregatingStreamingReport(
                    self.targets,
                    sc.StreamingClient(adapter, self.opts.streaming_task_id),
                    self.opts.report_config_path,
                    self.opts.keep_alive_streams,
                    self.opts.report_only_stages,
                )
            )

        if self.opts.json_line_report_file:
            report_list.append(results_report.JsonLineReport(self.opts.json_line_report_file))

        self._reports_generator = ar.ReportGenerator(
            self.opts,
            self.distbuild_graph,
            self.targets,
            tests,
            self.get_owners(),
            self.get_make_files(),
            results_dir,
            self._output_root,
            report_list,
        )
        test_node_listener.set_report_generator(self._reports_generator)
        self._build_results_listener.add(test_node_listener)
        self._build_results_listener.add(
            pr.BuildResultsListener(
                self.ctx.lite_graph,
                tests,
                self.ctx.mergers,
                self._reports_generator,
                test_results_path,
                self.opts,
            )
        )
        if self.opts.use_distbuild:
            self._slot_time_listener = pr.SlotListener(self.opts.statistics_out_dir)
            self._build_results_listener.add(self._slot_time_listener)

        if not self.opts.report_skipped_suites_only:
            self._reports_generator.add_configure_results(self.ctx.configure_errors)

        if self.opts.remove_result_node and (self.opts.report_skipped_suites or self.opts.report_skipped_suites_only):
            self._reports_generator.add_tests_results(
                self.ctx.stripped_tests, build_errors=None, node_build_errors_links=[]
            )

        if len(tests) == 0:
            self._reports_generator.finish_style_report()
            self._reports_generator.finish_tests_report()

        self._reports_generator.finish_configure_report()

    def _calc_exit_code(self):
        # Configuration errors result in an exit with error code 1
        # Test execution errors result in an exit with error code 10
        # If both errors are present (mode -k / --keep-going), the system exits with exit code 1
        # in order to separate standard test execution errors from test errors associated with configuration errors.
        # TODO see YA-1456
        # if self.ctx.configure_errors:
        #     return self.exit_code or error.ExitCodes.CONFIGURE_ERROR

        # XXX Don't try to inspect test statuses in listing mode.
        # Listing mode uses different test's info data channel and doesn't set proper test status
        if self.opts.run_tests and not self.opts.list_tests:
            if self.ctx.tests:
                return self.exit_code or get_suites_exit_code(self.ctx.tests, self.opts.test_fail_exit_code)
            else:
                # TODO Remove --no-tests-is-error option and fail with NO_TESTS_COLLECTED exit code by default. For more info see YA-1087
                # Return a special exit code if tests were requested, but no tests were run.
                if self.opts.no_tests_is_error:
                    return self.exit_code or core.error.ExitCodes.NO_TESTS_COLLECTED

        return self.exit_code

    def _test_console_report(self):
        suites = self.ctx.tests + self.ctx.stripped_tests

        broken_deps = False
        if self.exit_code:
            # Build is failed - search for broken deps for tests
            broken_deps = self.set_skipped_status_for_broken_suites(suites)

        test_results_console_printer.print_tests_results_to_console(self, suites)
        # Information about the error in the suite may be too high and not visible - dump explicit message after the report
        if broken_deps:
            self.app_ctx.display.emit_message("[[alt3]]SOME TESTS DIDN'T RUN DUE TO BUILD ERRORS[[rst]]")

    def _get_results_root(self):
        results_root = test_tools.get_results_root(self.opts)
        return results_root and results_root.replace("$(SOURCE_ROOT)", self.ctx.src_dir)

    def _finish_reports(self):
        if self._slot_time_listener:
            self._slot_time_listener.finish()

        if self._reports_generator is None:
            return

        logger.debug('Build is finished, process results')
        if not self.opts.report_skipped_suites_only:
            self._reports_generator.add_build_results(self.build_result)
        self._reports_generator.finish_build_report()

        if self.opts.remove_result_node:
            suites = self.ctx.stripped_tests
            if not self.opts.report_skipped_suites_only:
                suites += build_report.fill_suites_results(self, self.ctx.tests, self._output_root)
        else:
            suites = [t for t in self.ctx.tests if t.is_skipped()]
            if not self.opts.report_skipped_suites_only:
                suites += build_report.fill_suites_results(
                    self, [t for t in self.ctx.tests if not t.is_skipped()], self._output_root
                )

        report_prototype = collections.defaultdict(list)

        self._reports_generator.add_tests_results(
            suites, self.build_result.build_errors, self.build_result.node_build_errors_links, report_prototype
        )
        self._reports_generator.finish_tests_report()
        self._reports_generator.finish_style_report()
        self._reports_generator.finish()

    def make_report(self):
        return self._report.make_report() if self._report is not None else None

    def go(self):
        self._setup_build_root(self.opts.bld_root)
        self._setup_reports()
        self._setup_compact_for_gc()

        if not self.ctx.threads:
            self._finish_reports()
            self._generate_report()
            self._strip_cache(self.ctx.threads)
            release_all_data()
            return

        if exts.windows.on_win() and self.opts.create_symlinks and not self.opts.output_root:
            logger.warning(
                "Symlinks for the outputs are disabled on Windows. Use -o/--output option to explicitly specify the directory for the outputs"
            )

        try:
            result_analyzer = None  # using for --stat
            if self.opts.report_skipped_suites_only:
                self.exit_code = 0
            else:
                if self.ctx.graph and len(self.ctx.graph['graph']) == 0:
                    (
                        res,
                        err,
                        err_links,
                        tasks_metrics,
                        self.exit_code,
                        node_status_map,
                        exit_code_map,
                        result_analyzer,
                    ) = ({}, {}, {}, {}, 0, {}, {}, None)
                else:
                    (
                        res,
                        err,
                        err_links,
                        tasks_metrics,
                        self.exit_code,
                        node_status_map,
                        exit_code_map,
                        result_analyzer,
                    ) = self._dispatch_build(self._build_results_listener)
                (
                    errors,
                    errors_links,
                    failed_deps,
                    node_build_errors,
                    node_build_errors_links,
                ) = br.make_build_errors_by_project(self.ctx.lite_graph['graph'], err, err_links or {})
                build_metrics = st.make_targets_metrics(self.ctx.lite_graph['graph'], tasks_metrics)
                self.build_result = br.BuildResult(
                    errors,
                    failed_deps,
                    node_build_errors,
                    res,
                    build_metrics,
                    errors_links,
                    node_build_errors_links,
                    node_status_map,
                    exit_code_map,
                )

                if self.ctx.cache_test_statuses:
                    with stager.scope('cache_test_statuses'):
                        last_failed.cache_test_statuses(
                            res, self.ctx.tests, self.ctx.garbage_dir, self.opts.last_failed_tests
                        )

            if self.opts.print_test_console_report:
                self._test_console_report()
            if result_analyzer is not None:
                result_analyzer()
            self._finish_reports()
            self._generate_report()

            self.exit_code = self._calc_exit_code()

            if self.exit_code == core.error.ExitCodes.NO_TESTS_COLLECTED:
                self.app_ctx.display.emit_message("[[bad]]Failed - No tests collected[[rst]]")
            elif self.exit_code:
                self.app_ctx.display.emit_message('[[bad]]Failed[[rst]]')
            else:
                self.app_ctx.display.emit_message('[[good]]Ok[[rst]]')

            if self.ctx.create_symlinks:
                self._setup_repo_state()
                self.ctx.symlink_result.commit()

            if self.ctx.opts.get_deps and self.exit_code == 0:
                get_deps(self.ctx.opts.rel_targets, self.ctx.lite_graph, self.build_result, self.ctx.opts.get_deps)

            if self.opts.dump_raw_results and self.opts.output_root:
                self._dump_raw_build_results(self.opts.output_root)

            if (
                hasattr(self.ctx, 'yt_cached_results')
                and hasattr(self.ctx, 'yt_not_cached_results')
                and self.opts.output_root
            ):
                self._dump_yt_cache_nodes_by_status(self.opts.output_root)

            self._strip_cache(self.ctx.threads)

            return self.exit_code
        finally:
            self.ctx.cache.flush()
            release_all_data()
            post_local_cache_report()
            self.ctx.unlock()

    def _validate_opts(self):
        if self.opts.build_results_report_file and not self.opts.output_root:
            raise core.yarg.FlagNotSupportedException("--build-results-report must be used with not empty --output")
        if self.opts.junit_path and not self.opts.output_root:
            raise core.yarg.FlagNotSupportedException("--junit must be used with not empty --output")
        # Use os.path.commonpath when YA-71 is done (`import six` - keywords for simplifying the search for technical debt)
        if self.opts.output_root:
            abs_output = os.path.normpath(os.path.abspath(self.opts.output_root))
            abs_root = os.path.normpath(os.path.abspath(self.arc_root))
            if exts.fs.commonpath([abs_root, abs_output]).startswith(abs_root):
                self.app_ctx.display.emit_message(
                    '[[warn]]Output root is subdirectory of Arcadia root, this may cause non-idempotent build[[rst]]'
                )

    def _dispatch_build(self, callback):
        with stager.scope('dispatch_build'):
            if self.opts.use_distbuild:
                return self._build_distbs(callback)
            else:
                return self._build_local(callback)

    def _build_distbs(self, callback):
        from yalibrary.yandex.distbuild import distbs

        display = self.app_ctx.display

        patterns = ptrn.Patterns()
        patterns['SOURCE_ROOT'] = exts.path2.normpath(self.ctx.src_dir)

        if self.opts.ymake_bin and any(
            [self.opts.make_context_on_distbuild, self.opts.make_context_on_distbuild_only, self.opts.make_context_only]
        ):
            raise core.yarg.FlagNotSupportedException(
                "Context generation on distbuild with specified ymake binary is not supported yet"
            )

        if not self.opts.download_artifacts:
            logger.warning(
                'Distributed build does not download build and testing artifacts by default. '
                + 'Use -E/--download-artifacts option, see details in help.'
            )

        def upload_resources_to_sandbox():
            for resource in self.ctx.lite_graph.get('conf', {}).get('resources', []):
                if resource.get('resource', '').startswith("file:"):
                    import yalibrary.upload.uploader as uploader

                    logger.debug('Uploading resource ' + resource['resource'])
                    resource['resource'] = 'sbr:' + str(
                        uploader.do(paths=[os.path.abspath(resource['resource'][len("file:") :])], ttl=1)
                    )
                    logger.debug('Uploaded to ' + resource['resource'])

        def upload_repository_package():
            import devtools.ya.build.source_package as sp

            self.app_ctx.display.emit_status('Start to pack and upload inputs package')
            inputs_map = self.ctx.lite_graph['inputs']
            for node in self.ctx.lite_graph['graph']:
                node_inputs = dict((i, None) for i in node['inputs'])
                inputs_map = lg.union_inputs(inputs_map, node_inputs)
            repository_package = sp.pack_and_upload(self.opts, inputs_map, self.opts.arc_root)
            graph = self.ctx.lite_graph if self.ctx.opts.use_lite_graph else self.ctx.graph
            graph['conf']['repos'] = gp.make_tared_repositories_config(repository_package)

        def run_db():
            ready = None
            try:
                upload_resources_to_sandbox()
                graph = self.ctx.lite_graph if self.ctx.opts.use_lite_graph else self.ctx.graph

                if self.opts.repository_type == distbs_consts.DistbuildRepoType.TARED:
                    upload_repository_package()

                if self.opts.dump_distbuild_graph:
                    with open(self.opts.dump_distbuild_graph, 'w') as graph_file:
                        json.dump(graph, graph_file)

                def activate_callback(res=None, build_stage=None):
                    try:
                        for x in res or []:
                            self.ctx.task_context.dispatch_uid(x['uid'], x)
                            if callback:
                                callback(x)
                        if build_stage and callback:
                            callback(build_stage=build_stage)
                    except Exception as e:
                        logger.debug(
                            "Failed to activate: %s, exception %s",
                            ([x['uid'] for x in res] if res else build_stage),
                            str(e),
                        )
                        raise

                logger.debug("Waiting local executor to prepare")
                ready = self.ctx.local_runner_ready.wait()
                logger.debug("Local executor status: %s", str(ready))
                if ready:
                    logger.debug("Starting distbuild")
                    res = distbs.run_dist_build(
                        graph,
                        self.ctx.opts,
                        display,
                        activate_callback,
                        output_replacements=self.ctx.output_replacements,
                        evlog=getattr(self.app_ctx, 'evlog', None),
                        patterns=patterns,
                    )
                else:
                    logger.debug("Exit from local runner by exception. No local executor, hence no distbuild started")
                    res = collections.defaultdict(list)

                if self.opts.dump_distbuild_result:
                    with open(self.opts.dump_distbuild_result, 'w') as result_file:
                        json.dump(res, result_file)

                return res

            finally:
                if ready is None:
                    ready = self.ctx.local_runner_ready.wait()
                # Even if 'not ready', local executor may be partially initialized.
                if hasattr(self.ctx, 'task_context'):
                    logger.debug("Cleanup local executor: dispatch_all tasks, ready=%s", ready)
                    self.ctx.task_context.dispatch_all()
                else:
                    # ready should be False here
                    logger.debug("Local executor malfunction: task_context is not prepared, ready=%s", ready)

        def extract_exit_code_or_status(db_result):
            errors = list(db_result.get('failed_results', {}).get('reasons', {}).values())
            for x in errors:
                logger.debug("Failed result: %s", json.dumps(x, sort_keys=True))
            return max(max(item['exit_code'], item['status'] != 0) for item in errors) if errors else 0

        def extract_tasks_metrics(db_result):
            return db_result.get('tasks_metrics', {})

        def extract_build_errors(db_result):
            extract_build_errors_stage = stager.start('extract_build_errors')

            import exts.asyncthread

            def fetch_one(kv, mds_read_account=self.opts.mds_read_account):
                u, desc = kv
                stderr, links = distbs.extract_stderr(
                    desc, mds_read_account, download_stderr=self.opts.download_failed_nodes_stderr
                )
                return (
                    (u, patterns.fix(six.ensure_str(stderr))),
                    (u, links),
                    (u, desc['status']),
                    (u, desc.get('exit_code', 0)),
                )

            default_download_thread_count = self.ctx.threads + (self.ctx.opts.yt_store_threads or 3)
            download_thread_count = self.opts.stderr_download_thread_count or default_download_thread_count
            logger.debug(
                "Default download thread count is %i (%i + %i), actual is %i",
                default_download_thread_count,
                self.ctx.threads,
                (self.ctx.opts.yt_store_threads or 3),
                download_thread_count,
            )

            failed_items = list(db_result.get('failed_results', {}).get('reasons', {}).items())

            fetch_results = tuple(zip(*exts.asyncthread.par_map(fetch_one, failed_items, download_thread_count)))

            stderr_pairs, links_pairs, status_pairs, exit_code_map = fetch_results or ([], [], [], [])

            extract_build_errors_stage.finish()
            return dict(stderr_pairs), dict(links_pairs), dict(status_pairs), dict(exit_code_map)

        run_db_async = core_async.future(run_db, daemon=False)

        try:
            res, err, exit_code, local_execution_log, _ = self.ctx.runner(
                self.ctx, self.app_ctx, callback, output_replacements=self.ctx.output_replacements
            )
        finally:
            distbs_result = run_db_async()

        def result_analyzer():
            return bs.analyze_distbuild_result(
                distbs_result,
                self.distbuild_graph.get_graph(),
                self.opts.statistics_out_dir,
                self.opts,
                get_task_stats(),
                local_result=local_execution_log,
                ctx_stages=self.ctx.stage_times,
                ymake_stats=self.ctx.ymake_stats,
            )

        build_errors, build_errors_links, status_map, exit_code_map = extract_build_errors(distbs_result)
        return (
            res,
            build_errors,
            build_errors_links,
            extract_tasks_metrics(distbs_result),
            extract_exit_code_or_status(distbs_result),
            status_map,
            exit_code_map,
            result_analyzer,
        )

    def _build_local(self, callback):
        res, errors, exit_code, execution_log, exit_code_map = self.ctx.runner(
            self.ctx, self.app_ctx, callback, output_replacements=self.ctx.output_replacements
        )

        def extract_tasks_metrics():
            metrics = {}
            for u, data in six.iteritems(execution_log):
                if 'timing' in data and data['timing']:
                    elapsed = data['timing'][1] - data['timing'][0]
                    metrics[u] = {'elapsed': elapsed}
            return metrics

        def result_analyzer():
            return bs.analyze_local_result(
                execution_log,
                self.ctx.lite_graph,
                self.opts.statistics_out_dir,
                self.opts,
                set(errors.keys()),
                get_task_stats(),
                ctx_stages=self.ctx.stage_times,
                ymake_stats=self.ctx.ymake_stats,
            )

        if not self.opts.random_build_root:
            latest_path = os.path.join(self.opts.bld_dir, 'latest')
            if os.path.islink(latest_path):
                exts.fs.remove_file(latest_path)
            if not os.path.exists(latest_path):
                exts.fs.symlink(self.opts.bld_root, latest_path)

        return res, errors, None, extract_tasks_metrics(), exit_code, {}, exit_code_map, result_analyzer

    @func.lazy_property
    def targets(self):
        return self.distbuild_graph.get_targets()

    @func.lazy_property
    def distbuild_graph(self):
        return bp.DistbuildGraph(self.ctx.lite_graph)

    def _dump_raw_build_results(self, dest):
        try:
            fd = {str(k): v for k, v in six.iteritems(self.build_result.failed_deps)}
            self._dump_json(os.path.join(dest, 'failed_dependants.json'), fd)
            self._dump_json(os.path.join(dest, 'configure_errors.json'), self.ctx.configure_errors)
            self._dump_json(os.path.join(dest, 'ok_nodes.json'), self.build_result.ok_nodes)
            self._dump_json(os.path.join(dest, 'targets.json'), self.targets)
            be = {str(k): v for k, v in six.iteritems(self.build_result.build_errors)}
            self._dump_json(os.path.join(dest, 'build_errors.json'), be)
        except Exception:
            logging.exception("Error while dumping raw results")

    def _dump_yt_cache_nodes_by_status(self, dest):
        for name in ('yt_cached_results', 'yt_not_cached_results'):
            with open(os.path.join(dest, name + '.txt'), 'w') as f:
                f.write('\n'.join(getattr(self.ctx, name, [])))

    def set_skipped_status_for_broken_suites(self, suites):
        broken_deps = False
        for suite in suites:
            if not suite._errors and not suite.tests:
                suite.add_suite_error("[[bad]]skipped due to a failed build[[warn]]", const.Status.SKIPPED)
                broken_deps = True
        return broken_deps


def merge_pgo_profiles(profiles):
    all_profiles = [g for profile in profiles for g in glob.glob(profile)]
    if not all_profiles:
        raise EmptyProfilesListException('PGO profiles not found')
    if len(all_profiles) == 1:
        with open(all_profiles[0], 'rb') as f:
            if f.read(8) == b'\xfflprofi\x81':
                return all_profiles[0]
    hashes = [hashing.fast_filehash(fname) for fname in all_profiles]
    output = ''
    for h in sorted(hashes):
        output = hashing.fast_hash(output + h)
    output = 'merged.' + output + '.profdata'
    if not os.path.exists(output):
        subprocess.check_call([str(tools.tool('llvm-profdata')), 'merge', '-output', output] + all_profiles)
    logger.info('pgo merged profile name is %s', os.path.abspath(output))
    return output
