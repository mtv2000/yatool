PY23_LIBRARY()

STYLE_PYTHON()

PY_SRCS(
    canonize.py
)

PEERDIR(
    devtools/ya/app_config
    devtools/ya/exts
    devtools/ya/test/canon
    devtools/ya/test/const
    devtools/ya/test/dependency
    devtools/ya/test/filter
    devtools/ya/test/reports
    devtools/ya/test/result
    devtools/ya/test/test_types
    devtools/ya/test/util
    devtools/ya/yalibrary/yandex/sandbox/misc
)

IF (NOT YA_OPENSOURCE)
    PEERDIR(
        devtools/ya/test/dependency/sandbox_storage
    )
ENDIF()

END()

RECURSE_FOR_TESTS(
    tests
)
