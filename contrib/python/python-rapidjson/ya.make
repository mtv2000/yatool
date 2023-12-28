# Generated by devtools/yamaker (pypi).

PY3_LIBRARY()

VERSION(1.14)

LICENSE(MIT)

ADDINCL(
    contrib/python/python-rapidjson/rapidjson/include
)

NO_COMPILER_WARNINGS()

NO_LINT()

SRCS(
    rapidjson.cpp
)

PY_REGISTER(
    rapidjson
)

RESOURCE_FILES(
    PREFIX contrib/python/python-rapidjson/
    .dist-info/METADATA
    .dist-info/top_level.txt
    rapidjson/license.txt
    rapidjson/readme.md
)

END()

RECURSE_FOR_TESTS(
    tests
)
