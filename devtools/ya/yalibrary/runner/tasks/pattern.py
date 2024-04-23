import os
import sys
import logging
import base64
import tempfile
import time

import six

import core.error

from yalibrary.fetcher import resource_fetcher
from yalibrary.active_state import Cancelled
import yalibrary.worker_threads as worker_threads


class PreparePattern(object):
    def __init__(
        self, pattern, ctx, res_dir, build_root, resources_map, fetchers_storage, fetch_resource_if_need, execution_log
    ):
        self._pattern = pattern
        self._ctx = ctx
        self._res_dir = res_dir
        self._resources_map = resources_map
        self._fetchers_storage = fetchers_storage
        self._fetch_resource_if_need = fetch_resource_if_need

        self._percent = None
        self._error = None
        self._exit_code = 0
        self._build_root = build_root
        self._execution_log = execution_log

    @property
    def exit_code(self):
        return self._exit_code

    def __call__(self, *args, **kwargs):
        try:
            start_time = time.time()
            self._ctx.patterns[self._pattern] = self.fetch(self._resources_map[self._pattern])
            finish_time = time.time()
            self._execution_log["$({})".format(self._pattern)] = {
                'timing': (start_time, finish_time),
                'prepare': '',
                'type': 'tools',
            }
        except Cancelled:
            logging.debug("Fetching of the %s resource was cancelled", self._pattern)
            self._ctx.fast_fail()
            raise
        except Exception as e:
            if getattr(e, 'mute', False) is not True:
                logging.exception('Unable to fetch resource %s', self._pattern)

            self._exit_code = core.error.ExitCodes.INFRASTRUCTURE_ERROR if core.error.is_temporary_error(e) else 1

            self._ctx.fast_fail()

            self._error = '[[bad]]ERROR[[rst]]: ' + str(e)

    def fetch(self, item):
        platform = getattr(self._ctx.opts, 'host_platform', None)
        resource_desc = resource_fetcher.select_resource(item, platform)
        resource = resource_desc['resource']
        resource_type, resource_id = resource.split(':', 1)
        accepted_resource_types = {'file', 'https', 'base64'} | self._fetchers_storage.accepted_schemas()

        assert resource_type in accepted_resource_types, 'Resource schema {} not in accepted ({})'.format(
            resource_type, ', '.join(sorted(accepted_resource_types))
        )
        strip_prefix = resource_desc.get('strip_prefix')

        if resource_type in ({'https'} | self._fetchers_storage.accepted_schemas()):

            def progress_callback(percent):
                self._ctx.state.check_cancel_state()
                self._percent = percent

            return os.path.abspath(
                self._fetch_resource_if_need(
                    self._fetchers_storage.get_by_type(resource_type),
                    self._res_dir,
                    resource,
                    progress_callback,
                    self._ctx.state,
                    strip_prefix=strip_prefix,
                )
            )
        elif resource_type == 'file':
            return os.path.abspath(resource_id)
        elif resource_type == 'base64':
            dir_name = tempfile.mkdtemp(prefix="base64_resource-", dir=self._build_root)
            base_name, contents = resource_id.split(':', 1)
            with open(os.path.join(dir_name, base_name), 'w') as c:
                c.write(six.ensure_str(base64.b64decode(contents)))
            return dir_name

    def __str__(self):
        return 'Pattern(' + self._pattern + ')'

    def prio(self):
        return sys.maxsize

    def body(self):
        return self._error

    def status(self):
        str = '[[c:yellow]]PREPARE[[rst]] ' + '[[imp]]$(' + self._pattern + ')[[rst]]'
        if self._percent is not None:
            str += ' - %.1f%%' % self._percent
        return str

    def res(self):
        return worker_threads.ResInfo()

    def short_name(self):
        return 'pattern[{}]'.format(self._pattern)
