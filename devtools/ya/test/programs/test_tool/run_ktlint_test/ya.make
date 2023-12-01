PY23_LIBRARY()

PY_SRCS(
    run_ktlint_test.py
)

PEERDIR(
    devtools/ya/exts
    devtools/ya/test/const
    devtools/ya/test/facility
    devtools/ya/test/system/process
    devtools/ya/test/test_types
    devtools/ya/test/util
    devtools/ya/yalibrary/display
    devtools/ya/yalibrary/formatter
    devtools/ya/yalibrary/term
)

STYLE_PYTHON()

END()

RECURSE(
    tests
)
