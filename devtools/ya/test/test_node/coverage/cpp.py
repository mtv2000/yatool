import os
import logging
import itertools

from . import rigel

import build.gen_plan as gen_plan
import devtools.ya.test.dependency.testdeps as testdeps
import devtools.ya.test.dependency.uid as uid_gen
import exts.hashing
import test.common as test_common
import test.const
import test.util.tools as util_tools
import yalibrary.tools as tools

logger = logging.getLogger(__name__)


def _resolve_platform(platform_descriptor):
    return platform_descriptor.get("params", {}).get("match_root", "DEFAULT_LINUX_X86_64")


def is_cpp_coverage_requested(opts):
    return any(getattr(opts, name, False) for name in ('gcov_coverage', 'sancov_coverage', 'clang_coverage'))


def inject_gcov_coverage_nodes(graph, suites, resolvers_map, opts, platform_descriptor):
    coverage_prefix_filter = getattr(opts, 'coverage_prefix_filter', None)
    coverage_exclude_regexp = getattr(opts, 'coverage_exclude_regexp', None)

    gcda_node_uid = rigel.inject_coverage_merge_node(graph, suites, 'coverage.tar', 'coverage-merged.tar', opts=opts)
    gcno_node_uid = inject_collect_gcno_node(graph, opts=opts)
    jdk_resource = None
    for s in suites:
        jdk_resource = getattr(s, 'jdk_resource')
        if jdk_resource:
            break
    if getattr(opts, 'build_coverage_report', False):
        return [
            inject_calc_coverage_node(
                graph,
                gcno_node_uid,
                gcda_node_uid,
                coverage_prefix_filter,
                coverage_exclude_regexp,
                opts,
                '_'.join([suite.name for suite in suites]),
                jdk_resource,
            )
        ]
    return [gcno_node_uid, gcda_node_uid]


def inject_calc_coverage_node(
    graph,
    gcno_node_uid,
    gcda_node_uid,
    coverage_prefix_filter,
    coverage_exclude_regexp,
    opts,
    sonar_project_name,
    jdk_resource=None,
):
    deps = [gcno_node_uid, gcda_node_uid]

    for node in graph.get_graph()['graph']:
        for o in node['outputs']:
            if o.endswith('.gcno'):
                deps.append(node['uid'])
                break

    uid = uid_gen.get_random_uid("calc-coverage")

    gcno_path = "$(BUILD_ROOT)/all-gcno.tar"
    gcda_path = "$(BUILD_ROOT)/coverage-merged.tar"

    gcov_tool = tools.tool('gcov')  # XXX

    output_path = "$(BUILD_ROOT)/coverage.report.tar"
    coverage_info_script = "$(SOURCE_ROOT)/build/scripts/coverage-info.py"
    gcov_report = "$(BUILD_ROOT)/gcov_report.xml"

    # leave some cpu capacity for nodes execution in background
    # nthreads = max(1, getattr(opts, 'build_threads') - 2)
    result_cmd = [
        coverage_info_script,
        '--source-root',
        '$(SOURCE_ROOT)',
        '--output',
        output_path,
        '--gcno-archive',
        gcno_path,
        '--gcda-archive',
        gcda_path,
        '--gcov-tool',
        gcov_tool,
        # '--workers', str(nthreads),
    ]
    if getattr(opts, 'teamcity', False):
        result_cmd.extend(['--teamcity-stat-output'])
    if coverage_prefix_filter:
        result_cmd.extend(['--prefix-filter', coverage_prefix_filter])
    if coverage_exclude_regexp:
        result_cmd.extend(['--exclude-regexp', coverage_exclude_regexp])
    if getattr(opts, 'coverage_report_path'):
        result_cmd.extend(['--coverage-report-path', opts.coverage_report_path])
    inputs = [coverage_info_script]
    outputs = [output_path]
    if getattr(opts, 'sonar', False):
        import jbuild.gen.actions.sonar as sonar

        assert jdk_resource is not None
        result_cmd.extend(['--gcov-report', gcov_report, '--lcov-cobertura', tools.tool('lcov_cobertura')])
        outputs.append(gcov_report)

        sonar_script = "$(SOURCE_ROOT)/build/scripts/run_sonar.py"
        sonar_cmd = [
            sonar_script,
            '--sonar-scanner-jar-path',
            '$(SONAR_SCANNER)/sonar-scanner-cli-2.8.jar',
            '--sonar-scanner-main-class',
            'org.sonarsource.scanner.cli.Main',
            '--java-binary-path',
            jdk_resource + '/bin/java',
            '--gcov-report-path',
            gcov_report,
            '--source-root',
            '$(SOURCE_ROOT)',
            '--log-path',
            '$(BUILD_ROOT)/{}/.sonar.log'.format(exts.hashing.fast_hash(sonar_project_name)),
            'sonar.projectName=' + sonar_project_name,
            'sonar.projectKey=' + sonar_project_name,
            'sonar.cxx.coverage.reportPath=' + gcov_report,
            'sonar.source.encoding=UTF-8',
            'user.home=' + '$(BUILD_ROOT)/hamster',
        ]
        version = sonar.get_project_version(opts)
        if version:
            sonar_cmd.append('sonar.projectVersion=' + version)
        else:
            logger.warning(
                'Can\'t determine svn version for arcadia root %s, sonar.projectVersion will not be set automatically',
                opts.arc_root,
            )
        for key, value in sorted(opts.sonar_properties.items()):
            sonar_cmd.append(key + '=' + opts.sonar_properties[key])
        for arg in opts.sonar_java_args:
            sonar_cmd += ['--java-args', arg]
        node = {
            "node-type": test.const.NodeType.TEST_AUX,
            "broadcast": False,
            "inputs": [gcov_report, sonar_script],
            "uid": uid_gen.get_random_uid("sonar"),
            "cwd": "$(BUILD_ROOT)",
            "priority": 0,
            "deps": [uid],
            "env": {},
            "target_properties": {},
            "outputs": [],
            "tared_outputs": [],
            'kv': {
                "p": "JV",
                "pc": "light-blue",
                "show_out": True,
                "needs_resourceSONAR_SCANNER": True,
            },
            "cmds": [
                {
                    "cmd_args": test_common.get_python_cmd(opts=opts) + sonar_cmd,
                    "cwd": "$(BUILD_ROOT)",
                },
            ],
        }
        graph.append_node(node, add_to_result=True)

    node = {
        "node-type": test.const.NodeType.TEST_AUX,
        "broadcast": False,
        "inputs": inputs,
        "uid": uid,
        "cwd": "$(BUILD_ROOT)",
        "priority": 0,
        "deps": testdeps.unique(deps),
        "env": {},
        "target_properties": {},
        "outputs": outputs,
        "tared_outputs": [output_path],
        'kv': {
            "p": "CV",
            "pc": 'light-cyan',
            "show_out": True,
        },
        "cmds": [
            {
                "cmd_args": test_common.get_python_cmd(opts=opts) + result_cmd,
                "cwd": "$(BUILD_ROOT)",
            },
        ],
    }

    graph.append_node(node, add_to_result=True)

    return uid


def inject_collect_gcno_node(graph, opts=None):
    deps = []

    for node in graph.get_graph()['graph']:
        for o in node['outputs']:
            if o.endswith('.gcno'):
                deps.append(node['uid'])
                break

    uid = uid_gen.get_random_uid("gcno-collect")

    output_path = "$(BUILD_ROOT)/all-gcno.tar"
    find_and_tar_script = "$(SOURCE_ROOT)/build/scripts/find_and_tar.py"

    result_cmd = [find_and_tar_script, output_path, '.gcno']

    node = {
        "node-type": test.const.NodeType.TEST_AUX,
        "broadcast": False,
        "inputs": [find_and_tar_script],
        "uid": uid,
        "cwd": "$(BUILD_ROOT)",
        "priority": 0,
        "deps": testdeps.unique(deps),
        "env": {},
        "target_properties": {},
        "outputs": [output_path],
        'kv': {
            "p": "CV",
            "pc": 'light-cyan',
            "show_out": True,
        },
        "cmds": [
            {
                "cmd_args": test_common.get_python_cmd(opts=opts) + result_cmd,
                "cwd": "$(BUILD_ROOT)",
            },
        ],
    }

    graph.append_node(node, add_to_result=False)

    return uid


def inject_sancov_resolve_nodes(graph, suites, coverage_tar_name, result_filename, opts=None, platform_descriptor=None):
    resolve_uids = []
    resolved_covdata = []
    platform_name = _resolve_platform(platform_descriptor)
    for suite in suites:
        uids_outputs = rigel.get_suite_binary_deps(suite, graph)
        if not uids_outputs:
            continue

        input_filename = suite.work_dir(coverage_tar_name)
        output_path = suite.work_dir(result_filename)
        log_path = suite.work_dir("sancov_resolve.log")
        resolved_covdata.append(output_path)

        cmd = util_tools.get_test_tool_cmd(opts, "resolve_sancov_coverage", suite.global_resources) + [
            "--sancov-tool",
            "$({})/bin/sancov".format(platform_name),
            "--coverage-path",
            input_filename,
            "--output",
            output_path,
            "--log-path",
            log_path,
            "--source-root",
            "$(SOURCE_ROOT)",
        ]
        # sancov isn't resolved, that why we should specify certain binaries
        # to correctly symbolize the addresses

        test_uids = suite.result_uids
        uids, binaries = zip(*uids_outputs)
        test_uids.extend(uids)

        uid = uid_gen.get_uid(test_uids, "sancov_resolve")
        resolve_uids.append(uid)

        inputs = set()
        for output in binaries:
            if output not in inputs:
                cmd += ["--target-binary", output]
                inputs.add(output)

        node = {
            "node-type": test.const.NodeType.TEST_AUX,
            "cache": True,
            "broadcast": False,
            "inputs": list(inputs),
            "uid": uid,
            "cwd": "$(BUILD_ROOT)",
            "priority": 0,
            "deps": testdeps.unique(test_uids),
            "env": {},
            "target_properties": {
                "module_lang": suite.meta.module_lang,
            },
            "outputs": [output_path, log_path],
            'kv': {
                "p": "RC",
                "pc": 'cyan',
                "show_out": True,
            },
            "cmds": [
                {
                    "cmd_args": cmd,
                    "cwd": "$(BUILD_ROOT)",
                },
            ],
        }
        graph.append_node(node)

    return resolve_uids, resolved_covdata


def inject_create_sancov_coverage_report_node(graph, resolve_node_uids, inputs, opts, global_resources):
    output_path = "$(BUILD_ROOT)/coverage.report.tar"
    uid = uid_gen.get_uid(resolve_node_uids, "sancov_report")

    cmd = util_tools.get_test_tool_cmd(opts, "build_sancov_coverage_report", global_resources) + [
        "--output",
        output_path,
        "--source-root",
        "$(SOURCE_ROOT)",
    ]
    for coverage_path in inputs:
        cmd += ["--coverage-path", coverage_path]

    node = {
        "node-type": test.const.NodeType.TEST_AUX,
        "broadcast": False,
        "inputs": inputs,
        "uid": uid,
        "cwd": "$(BUILD_ROOT)",
        "priority": 0,
        "deps": resolve_node_uids,
        "env": {},
        "target_properties": {},
        "outputs": [output_path],
        "tared_outputs": [output_path],
        'kv': {
            "p": "CV",
            "pc": 'light-cyan',
            "show_out": True,
        },
        "cmds": [
            {
                'cmd_args': cmd,
                'cwd': '$(BUILD_ROOT)',
            }
        ],
    }
    graph.append_node(node, add_to_result=True)

    return uid


def inject_clang_coverage_unify_node(graph, suite, clang_resolver_uid, raw_resolved_filename, result_filename, opts):
    input_filename = suite.work_dir(raw_resolved_filename)
    output_path = suite.work_dir(result_filename)

    outputs = [output_path]

    cmd = util_tools.get_test_tool_cmd(opts, "unify_clang_coverage", suite.global_resources) + [
        "--raw-coverage-path",
        input_filename,
        "--output",
        output_path,
    ]

    if opts.coverage_prefix_filter:
        cmd += [
            "--prefix-filter",
            opts.coverage_prefix_filter,
        ]

    if opts.coverage_exclude_regexp:
        cmd += [
            "--exclude-regexp",
            opts.coverage_exclude_regexp,
        ]

    deps = [clang_resolver_uid]
    uid = uid_gen.get_uid(
        deps + [str(opts.coverage_exclude_regexp), str(opts.coverage_prefix_filter)], "resolve_raw_clangcov"
    )

    node = {
        "node-type": test.const.NodeType.TEST_AUX,
        "cache": True,
        "broadcast": False,
        "inputs": [input_filename],
        "uid": uid,
        "cwd": "$(BUILD_ROOT)",
        "priority": 0,
        "deps": testdeps.unique(deps),
        "env": {},
        "target_properties": {
            "module_lang": suite.meta.module_lang,
        },
        "outputs": testdeps.unique(outputs),
        'kv': {
            "p": "RC",
            "pc": 'cyan',
            "show_out": True,
        },
        "requirements": gen_plan.get_requirements(
            opts,
            {
                "cpu": 4,
                "network": "restricted",
            },
        ),
        "cmds": [
            {
                "cmd_args": cmd,
                "cwd": "$(BUILD_ROOT)",
            },
        ],
    }
    graph.append_node(node, add_to_result=True)
    return uid


def inject_clang_coverage_resolve_node(
    graph, suite, coverage_tar_name, result_filename, binary_uid, binary_path, opts=None, platform_descriptor=None
):
    deps = suite.result_uids + [binary_uid]
    # Take into account binary name, because all binaries from one package will have the same uid
    uid = uid_gen.get_uid(deps + [binary_path], "resolve_clangcov")

    input_filename = suite.work_dir(coverage_tar_name)
    output_path = suite.work_dir(result_filename)
    log_path = suite.work_dir("clangcov_resolve.{}.{}.log".format(os.path.basename(binary_path), binary_uid))
    timeout = 30 * 60  # 30 mins
    platform_name = _resolve_platform(platform_descriptor)
    cmd = util_tools.get_test_tool_cmd(opts, "resolve_clang_coverage", suite.global_resources) + [
        "--llvm-profdata-tool",
        "$({})/bin/llvm-profdata".format(platform_name),
        "--llvm-cov-tool",
        "$({})/bin/llvm-cov".format(platform_name),
        "--coverage-path",
        input_filename,
        "--target-binary",
        binary_path,
        "--output",
        output_path,
        "--log-path",
        log_path,
        "--source-root",
        "$(SOURCE_ROOT)",
        "--timeout",
        str(timeout),
    ]

    if opts.use_distbuild or opts.coverage_verbose_resolve:
        cmd += ["--log-level", "DEBUG"]

    node = {
        "node-type": test.const.NodeType.TEST_AUX,
        "cache": True,
        "broadcast": False,
        "inputs": [input_filename, binary_path],
        "uid": uid,
        "cwd": "$(BUILD_ROOT)",
        "priority": 0,
        "deps": testdeps.unique(deps),
        "env": {},
        "target_properties": {
            "module_lang": suite.meta.module_lang,
        },
        "outputs": [output_path, log_path],
        'kv': {
            "p": "RC",
            "pc": 'cyan',
            "show_out": True,
        },
        "requirements": gen_plan.get_requirements(
            opts,
            {
                "cpu": 4,
                "network": "restricted",
            },
        ),
        "timeout": timeout,
        "cmds": [
            {
                "cmd_args": cmd,
                "cwd": "$(BUILD_ROOT)",
            },
        ],
    }
    graph.append_node(node, add_to_result=False)
    return uid


def inject_create_clang_coverage_report_node(graph, suites, coverage_tar_name, opts, platform_descriptor):
    output_path = os.path.join("$(BUILD_ROOT)", "coverage.report.tar")
    log_path = os.path.join("$(BUILD_ROOT)", "build_clang_coverage_report.log")
    all_resources = {}
    for suite in suites:
        all_resources.update(suite.global_resources)

    platform_name = _resolve_platform(platform_descriptor)
    platform_variable = "$({})".format(platform_name)
    cmd = util_tools.get_test_tool_cmd(opts, "build_clang_coverage_report", all_resources) + [
        "--output",
        output_path,
        "--source-root",
        "$(SOURCE_ROOT)",
        "--llvm-profdata-tool",
        os.path.join(platform_variable, "bin", "llvm-profdata"),
        "--llvm-cov-tool",
        os.path.join(platform_variable, "bin", "llvm-cov"),
        "--log-path",
        log_path,
    ]

    if opts.use_distbuild or opts.coverage_verbose_resolve:
        cmd += ["--log-level", "DEBUG"]

    if opts.coverage_prefix_filter:
        cmd += [
            "--prefix-filter",
            opts.coverage_prefix_filter,
        ]

    if opts.coverage_exclude_regexp:
        cmd += [
            "--exclude-regexp",
            opts.coverage_exclude_regexp,
        ]

    test_uids = set()
    inputs = set()
    for suite in suites:
        # Skip go binaries - they are not instrumented.
        uids_outputs = rigel.get_suite_binary_deps(suite, graph, skip_module_lang=['go'])
        # There might be no binaries in exectests, for example
        # https://a.yandex-team.ru/arc/trunk/arcadia/maps/config/juggler/geo_juggler/mobnavi_legacy/ya.make
        if not uids_outputs:
            continue

        test_uids.update(suite.result_uids)

        input_filename = suite.work_dir(coverage_tar_name)
        uids, binaries = zip(*uids_outputs)
        test_uids.update(uids)

        cmd += ["--coverage-path", input_filename]
        inputs.add(input_filename)

        for output in binaries:
            if output not in inputs:
                cmd += ["--target-binary", output]
                inputs.add(output)

    uid = uid_gen.get_uid(
        list(test_uids) + [str(opts.coverage_prefix_filter), str(opts.coverage_exclude_regexp)], "clangcov_report"
    )

    node = {
        "node-type": test.const.NodeType.TEST_AUX,
        "broadcast": False,
        "inputs": list(inputs),
        "uid": uid,
        "cwd": "$(BUILD_ROOT)",
        "priority": 0,
        "deps": testdeps.unique(test_uids),
        "env": {},
        "target_properties": {},
        "outputs": [output_path, log_path],
        "tared_outputs": [output_path],
        'kv': {
            "p": "CV",
            "pc": 'light-cyan',
            "show_out": True,
        },
        "cmds": [
            {
                'cmd_args': cmd,
                'cwd': '$(BUILD_ROOT)',
            }
        ],
    }
    graph.append_node(node, add_to_result=True)

    return uid


def inject_sancov_coverage_nodes(graph, suites, resolvers_map, opts, platform_descriptor):
    node_uids, outputs = inject_sancov_resolve_nodes(
        graph,
        suites,
        'coverage.tar',
        test.const.CPP_COVERAGE_RESOLVED_FILE_NAME,
        opts=opts,
        platform_descriptor=platform_descriptor,
    )
    all_resources = {}
    for suite in suites:
        all_resources.update(suite.global_resources)
    if getattr(opts, 'build_coverage_report', False):
        report_node_uid = inject_create_sancov_coverage_report_node(graph, node_uids, outputs, opts, all_resources)
        return [report_node_uid]
    return node_uids


def inject_clang_coverage_nodes(graph, suites, resolvers_map, opts, platform_descriptor):
    resolved_pattern = "%s.{}%s" % os.path.splitext(test.const.CPP_COVERAGE_RESOLVED_FILE_NAME)
    target_suites = [s for s in suites if s.get_type() in test.const.CLANG_COVERAGE_TEST_TYPES]

    result = []
    for suite in target_suites:
        resolvers = []
        names = set()
        # Don't resolve all clang coverage from suite in a single node.
        # Otherwise, in some degenerate complex cases it may took an enormous amount of time.
        # Skip go binaries - they are not instrumented.
        for uid, binary in rigel.get_suite_binary_deps(suite, graph, skip_module_lang=['go']):
            binname = os.path.basename(binary)
            filename = binname
            for i in itertools.count():
                if filename not in names:
                    names.add(filename)
                    break
                filename = "{}.{}".format(binname, i)

            resolved_filename = resolved_pattern.format(filename)
            raw_resolved_filename = ("%s.{}.{}%s" % os.path.splitext(resolved_filename)).format("raw", uid)
            raw_resolve_uid = inject_clang_coverage_resolve_node(
                graph,
                suite,
                'coverage.tar',
                raw_resolved_filename,
                uid,
                binary,
                opts=opts,
                platform_descriptor=platform_descriptor,
            )

            resolve_uid = inject_clang_coverage_unify_node(
                graph, suite, raw_resolve_uid, raw_resolved_filename, resolved_filename, opts
            )
            resolvers.append(resolve_uid)
            if resolvers_map is not None:
                resolvers_map[resolve_uid] = (resolved_filename, suite)

        if resolvers:
            # There is no easy way to know without a graph whether the nodes have completed successfully.
            # That's why we accumulate all resolve nodes from suite to the single lightweight node,
            # which will create certain file if all deps are successfully executed. This file will be checked
            # in task later to find suites with resolve problems.
            result.append(inject_coverage_resolve_awaiting_node(graph, suite, resolvers, opts))

    if getattr(opts, 'build_coverage_report', False):
        report_node_uid = inject_create_clang_coverage_report_node(
            graph, target_suites, 'coverage.tar', opts, platform_descriptor
        )
        result.append(report_node_uid)

    return result


def inject_coverage_resolve_awaiting_node(graph, suite, deps, opts=None):
    uid = uid_gen.get_uid(deps, "clang_cov_await")

    output_path = suite.work_dir("clangcov_resolve.done")
    script_append_file = '$(SOURCE_ROOT)/build/scripts/append_file.py'

    cmd = test_common.get_python_cmd(opts=opts) + [
        script_append_file,
        output_path,
        "1",
    ]

    node = {
        "node-type": test.const.NodeType.TEST_AUX,
        "cache": True,
        "broadcast": False,
        "inputs": [script_append_file],
        "uid": uid,
        "cwd": "$(BUILD_ROOT)",
        "priority": 0,
        "deps": deps,
        "env": {},
        "target_properties": {
            "module_lang": suite.meta.module_lang,
        },
        "outputs": [output_path],
        'kv': {
            "p": "RC",
            "pc": 'cyan',
        },
        "cmds": [
            {
                "cmd_args": cmd,
                "cwd": "$(BUILD_ROOT)",
            },
        ],
    }
    graph.append_node(node, add_to_result=True)
    return uid
