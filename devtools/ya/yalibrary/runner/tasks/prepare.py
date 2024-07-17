import sys
import logging
import six.moves.queue as queue

import core.error
import exts.uniq_id
import yalibrary.worker_threads as worker_threads
from yalibrary.runner import topo

from .resource import PrepareResource


logger = logging.getLogger(__name__)


class NodeResolveStatus:
    LOCAL = 0
    DIST = 1
    EXEC = 2
    ERROR = 3


def _get_node_resolve_status(node, local_cache, dist_cache, opts):
    cacheable = not opts.clear_build and node.cacheable
    if not cacheable:
        return NodeResolveStatus.EXEC

    if local_cache.has(node.uid):
        return NodeResolveStatus.LOCAL

    should_try_dist_cache = dist_cache and dist_cache.fits(node)
    if not should_try_dist_cache:
        return NodeResolveStatus.EXEC

    resolve_dist = opts.dist_cache_late_fetch or dist_cache.has(node.uid)
    if resolve_dist:
        return NodeResolveStatus.DIST

    if opts.yt_store_exclusive:
        return NodeResolveStatus.ERROR

    return NodeResolveStatus.EXEC


class UniqueTask(object):
    def __str__(self):
        raise ImportError('Missing __str__ implementation')

    def uid(self):
        return '{}-{}'.format(str(self), exts.uniq_id.gen16())


class PrepareAllNodesTask(UniqueTask):
    node_type = 'PrepareAllNodes'

    def __init__(self, nodes, ctx, cache, dist_cache):
        self._nodes = nodes
        self._ctx = ctx
        self._cache = cache
        self._dist_cache = dist_cache
        self._exit_code = 0

    @property
    def exit_code(self):
        return self._exit_code

    def __call__(self, *args, **kwargs):
        self._ctx.signal_ready()

        q = queue.Queue()
        tp = topo.Topo()

        touch_mode = not self._ctx.opts.clear_build and self._ctx.opts.strip_cache and hasattr(self._cache, 'compact')
        results = []
        for node in self._nodes:
            if node.is_result_node:
                q.put(node)
                tp.add_node(node)
                results.append(node)
                node.refcount += 1

            if touch_mode and node.cacheable:
                # touch node.uid for aggressive compaction
                self._cache.has(node.uid)

        while not q.empty():
            node = q.get()

            for x in node.dep_nodes():
                x.max_dist = max(x.max_dist, node.max_dist + 1)

            resolve_status = _get_node_resolve_status(node, self._cache, self._dist_cache, self._ctx.opts)

            if resolve_status == NodeResolveStatus.ERROR:
                logger.error("Failed to find {0} in the distributed cache".format(node))
                self._exit_code = core.error.ExitCodes.YT_STORE_FETCH_ERROR
                self._ctx.fast_fail(fatal=True)
                return

            elif resolve_status == NodeResolveStatus.LOCAL:
                self._ctx.task_cache(node, self._ctx.restore_from_cache)
                tp.schedule_node(node, when_ready=tp.notify_dependants)

            elif resolve_status == NodeResolveStatus.DIST:
                self._ctx.task_cache(node, self._ctx.restore_from_dist_cache)
                tp.schedule_node(node, when_ready=tp.notify_dependants)

            else:
                for x in node.dep_nodes():
                    if x not in tp:
                        q.put(x)
                        tp.add_node(x)
                    tp.add_deps(node, x)

                def add_run_node(node, *args, **kwargs):
                    deps = (
                        [self._ctx.task_cache(x) for x in node.dep_nodes()]
                        + [self._ctx.pattern_cache(x) for x in node.unresolved_patterns()]
                        + [
                            self._ctx.resource_cache(
                                tuple(sorted(x.items())), deps=PrepareResource.dep_resources(self._ctx, x)
                            )
                            for x in node.resources
                        ]
                    )
                    self._ctx.task_cache(node, self._ctx.run_node, deps=deps)
                    tp.notify_dependants(node)

                tp.schedule_node(node, when_ready=add_run_node)

        # Sanity check
        unscheduled = tp.get_unscheduled()
        assert not unscheduled, "Unscheduled {} tasks found: {}".format(len(unscheduled), list(unscheduled)[:10])

        if not self._ctx.opts.eager_execution:
            for node in results:
                self._ctx.runq.add(
                    self._ctx.result_node(node), deps=[self._ctx.task_cache(node), self._ctx.clean_symres_task]
                )

    def __str__(self):
        return 'PrepareAllNodes'

    def prio(self):
        return sys.maxsize

    def res(self):
        return worker_threads.ResInfo()

    def short_name(self):
        return 'prepare_all_nodes'


class PrepareAllDistNodesTask(UniqueTask):
    node_type = 'PrepareAllDistNodes'

    def __init__(self, nodes, ctx, download_artifacts, results):
        self._nodes = nodes
        self._ctx = ctx
        self._download_artifacts = download_artifacts
        self._results = results

    def __call__(self, *args, **kwargs):
        if not self._download_artifacts:
            self._ctx.signal_ready()
            return

        result_nodes = self._results
        for node in result_nodes:
            node.refcount += 1
            self._ctx.task_cache(node, self._ctx.run_dist_node, dispatch=False)
            if not self._ctx.opts.eager_execution:
                self._ctx.runq.add(
                    self._ctx.result_node(node), deps=[self._ctx.task_cache(node), self._ctx.clean_symres_task]
                )

        self._ctx.signal_ready()

    def __str__(self):
        return 'PrepareAllDistNodes'

    def prio(self):
        return sys.maxsize

    def res(self):
        return worker_threads.ResInfo(cpu=1)

    def short_name(self):
        return 'prepare_all_dist_nodes'


class PrepareNodeTask(object):
    node_type = 'PrepareNode'

    def __init__(self, node, ctx, cache, dist_cache):
        self._node = node
        self._ctx = ctx
        self._cache = cache
        self._dist_cache = dist_cache

    def __call__(self, *args, **kwargs):
        resolve_status = _get_node_resolve_status(self._node, self._cache, self._dist_cache, self._ctx.opts)

        if resolve_status == NodeResolveStatus.LOCAL:
            self._ctx.runq.add(self._ctx.restore_from_cache(self._node), joint=self)

        elif resolve_status == NodeResolveStatus.DIST:
            self._ctx.runq.add(self._ctx.restore_from_dist_cache(self._node), joint=self)

        else:
            self._ctx.exec_run_node(self._node, self)

    def __str__(self):
        return 'Prepare({})'.format(str(self._node))

    def prio(self):
        return sys.maxsize

    def res(self):
        return worker_threads.ResInfo()

    def short_name(self):
        return 'prepare[{}]'.format(self._node.kv.get('p', '??'))

    @property
    def uid(self):
        return 'prepare-{}'.format(self._node.uid)
