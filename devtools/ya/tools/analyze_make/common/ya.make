PY3_LIBRARY()

PY_SRCS(
    __init__.py
)

PEERDIR(
    devtools/ya/exts
    devtools/ya/yalibrary/display
    devtools/ya/yalibrary/evlog
    devtools/ya/yalibrary/formatter
)

STYLE_PYTHON()

END()
