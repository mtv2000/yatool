LIBRARY()

SRCS(
    platform.cpp
    platform_map.cpp
)

PEERDIR(
    library/cpp/digest/md5
    library/cpp/json
)

END()

RECURSE_FOR_TESTS(
    ut
)
