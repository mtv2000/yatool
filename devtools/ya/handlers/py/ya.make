
PY3_LIBRARY()

PY_SRCS(
    NAMESPACE handlers.py
    __init__.py
)

PEERDIR(
    devtools/ya/app
    devtools/ya/build
    devtools/ya/build/build_opts
    devtools/ya/core
    devtools/ya/core/config
    devtools/ya/core/yarg
    devtools/ya/exts
    devtools/ya/yalibrary/makelists
    library/python/filelock
    library/python/fs
    library/python/resource
)

END()

RECURSE_FOR_TESTS(
    bin
)
