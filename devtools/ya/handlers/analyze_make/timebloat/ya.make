PY3_LIBRARY()

PY_SRCS(
    NAMESPACE handlers.analyze_make.timebloat
    __init__.py
)

PEERDIR(
    devtools/ya/handlers/analyze_make/timebloat/html
    devtools/ya/core/resource
    devtools/ya/exts
    devtools/ya/tools/analyze_make/common
    library/python/resource
)

STYLE_PYTHON()

END()
