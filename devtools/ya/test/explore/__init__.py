# coding: utf-8

import os
import logging

from devtools.ya.test import dartfile
from test.test_types import (
    benchmark,
    boost_test,
    clang_tidy,
    common as types_common,
    cov_test,
    custom_lint,
    ext_resource,
    fuzz_test,
    go_test,
    gtest,
    java_style,
    junit,
    library_ut,
    py_test,
    ts_test,
)
from test.util import tools

logger = logging.getLogger(__name__)

SUITE_MAP = {
    'custom_lint': custom_lint.CustomLintTestSuite,
    'boost.test': boost_test.BoostTestSuite,
    'check.data': ext_resource.CheckDataSbrTestSuite,
    'check.external': ext_resource.CheckExternalTestSuite,
    'check.mds': ext_resource.CheckMDSTestSuite,
    'check.resource': ext_resource.CheckResourceTestSuite,
    'clang_tidy': clang_tidy.ClangTidySuite,
    'coverage.extractor': cov_test.CoverageExtractorTestSuite,
    'eslint': ts_test.EslintTestSuite,
    'exectest': py_test.ExecTest,
    'fuzz.test': fuzz_test.FuzzTestSuite,
    'g_benchmark': benchmark.GBenchmarkSuite,
    'go.bench': go_test.GoBenchSuite,
    'go.test': go_test.GoTestSuite,
    'gofmt': py_test.GoFmtTestSuite,
    'govet': py_test.GoVetTestSuite,
    'gunittest': gtest.GUnitTestSuite,
    'hermione': ts_test.HermioneTestSuite,
    'java.dependency.test': py_test.ClasspathClashTestSuite,
    'java.style': java_style.JavaStyleTestSuite,
    'jest': ts_test.JestTestSuite,
    'junit.test': junit.JavaTestSuite,
    'junit5.test': junit.Junit5TestSuite,
    'ktlint': java_style.KtlintTestSuite,
    'playwright': ts_test.PlaywrightTestSuite,
    'py.imports': py_test.CheckImportsTestSuite,
    'py3test.bin': py_test.Py3TestBinSuite,
    'pytest.bin': py_test.PyTestBinSuite,
    'tsc_typecheck': ts_test.TscTypecheckTestSuite,
    'unittest.py': library_ut.UnitTestSuite,
    'y_benchmark': benchmark.YBenchmarkSuite,
}


# TODO naming
def generate_tests_by_dart(
    dart_content, target_platform_descriptor=None, multi_target_platform_run=False, opts=None, with_wine=None
):
    darts = dartfile.parse_dart(dart_content.split('\n'))

    suites = []
    darts = dartfile.merge_darts(darts)
    for dart_info in darts:
        suite = gen_suite(dart_info, target_platform_descriptor, multi_target_platform_run, with_wine)
        if suite:
            suites.append(suite)

    suites_dict = {}
    for suite in suites:
        suite_uid = dartfile.get_suite_id(suite)
        if suite_uid in suites_dict:
            existing_suite = suites_dict[suite_uid]
            if not all(
                [
                    not existing_suite.is_skipped(),
                    existing_suite.fork_test_files_requested(opts),
                    not suite.is_skipped(),
                    suite.fork_test_files_requested(opts),
                ]
            ):
                logger.error(
                    'Found more than one test with the same name %s in %s, will test a random one',
                    suite.name,
                    suite.project_path,
                )
        else:
            suites_dict[suite_uid] = suite
    return suites_dict.values()


def gen_suite(dart_info, target_platform_descriptor=None, multi_target_platform_run=False, with_wine=None):
    script_rel_path = dart_info['SCRIPT-REL-PATH']
    suite = SUITE_MAP.get(script_rel_path)

    if suite:
        try:
            _suite = suite(
                dart_info,
                target_platform_descriptor=target_platform_descriptor,
                multi_target_platform_run=multi_target_platform_run,
            )
            if with_wine:
                assert with_wine in ('wine32', 'wine64'), 'unexpected wine type (use wine32 or wine64)'
                if with_wine == 'wine32':
                    _suite.wine_path = tools.get_wine32_path(_suite.global_resources)
                else:
                    _suite.wine_path = tools.get_wine64_path(_suite.global_resources)
            return _suite
        except Exception as e:
            logger.exception("%s - for %r suite", e, suite)
            raise
    else:
        logger.warn('Unable to detect type of test by SCRIPT-REL-PATH {}'.format(script_rel_path))


def generate_diff_tests(opts, target_platform_descriptor):
    revision = opts.test_diff or "HEAD"
    project_path = os.path.relpath(opts.abs_targets[0], opts.arc_root)
    return [types_common.DiffTestSuite(project_path, revision, target_platform_descriptor=target_platform_descriptor)]
