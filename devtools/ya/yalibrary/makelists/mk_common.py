# change extremely carefully
SAFE_JOIN_MACROS = {
    'CFLAGS',
    'CXXFLAGS',
    'OWNER',
    'PEERDIR',
    'PY_SRCS',
    'RECURSE',
    'RECURSE_ROOT_RELATIVE',
    'SRCDIR',
    'SRCS',
}

PROJECT_MACROS = {
    'AAR_CONTRIB',
    'BENCHMARK',
    'BOOSTTEST',
    'BOOSTTEST_WITH_MAIN',
    'CI_GROUP',
    'DEV_DLL_PROXY',
    'DLL',
    'DLL_JAVA',
    'DOCS',
    'DYNAMIC_LIBRARY',
    'ESP_BOOTLOADER',
    'ESP_LIBRARY',
    'ESP_PROGRAM',
    'EXECTEST',
    'EXTERNAL_JAVA_LIBRARY',
    'FAT_OBJECT',
    'GO_LIBRARY',
    'GO_PROGRAM',
    'GO_TEST',
    'GO_TEST_FOR',
    'GTEST',
    'G_BENCHMARK',
    'JAR_LIBRARY',
    'JAVA_CONTRIB',
    'JAVA_CONTRIB_PROGRAM',
    'JAVA_CONTRIB_PROXY',
    'JAVA_LIBRARY',
    'JAVA_PROGRAM',
    'JAVA_PROTO_LIBRARY',
    'JTEST',
    'LIBRARY',
    'METAQUERY',
    'PACKAGE',
    'PROGRAM',
    'PROTO_LIBRARY',
    'PY23_LIBRARY',
    'PY23_NATIVE_LIBRARY',
    'PY23_TEST',
    'PY2MODULE',
    'PY2TEST',
    'PY2_LIBRARY',
    'PY2_PROGRAM',
    'PY3TEST',
    'PY3_LIBRARY',
    'PY3_PROGRAM',
    'PYTEST_BIN',
    'PY_LIBRARY',
    'RESOURCES_LIBRARY',
    'SANDBOX_PY23_3_TASK',
    'SANDBOX_PY23_TASK',
    'SANDBOX_PY3_TASK',
    'SANDBOX_TASK',
    'TOOL',
    'TS_NEXT',
    'TS_PACKAGE',
    'TS_TEST_JEST_FOR',
    'TS_TSC',
    'TS_VITE',
    'TS_WEBPACK',
    'UDF',
    'UDF_LIB',
    'UNION',
    'UNITTEST',
    'UNITTEST_FOR',
    'UNITTEST_WITH_CUSTOM_ENTRY_POINT',
    'WAR_CONTRIB',
    'YQL_UDF',
}

V_END = 'ThisIsTheEnd'


class MkLibException(Exception):
    pass
