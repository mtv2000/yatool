PY3_LIBRARY()

STYLE_PYTHON()

PY_SRCS(
    run_skipped_test.py
)

PEERDIR(
    devtools/ya/test/common
    devtools/ya/test/const
    devtools/ya/test/test_types
)

END()
