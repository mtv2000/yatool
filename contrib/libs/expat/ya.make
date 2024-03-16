# Generated by devtools/yamaker from nixpkgs 22.11.

LIBRARY()

VERSION(2.6.2)

ORIGINAL_SOURCE(https://github.com/libexpat/libexpat/releases/download/R_2_6_2/expat-2.6.2.tar.xz)

LICENSE(
    CC0-1.0 AND
    JSON AND
    MIT
)

LICENSE_TEXTS(.yandex_meta/licenses.list.txt)

ADDINCL(
    contrib/libs/expat
    contrib/libs/expat/lib
)

NO_COMPILER_WARNINGS()

NO_RUNTIME()

CFLAGS(
    -DHAVE_CONFIG_H
)

IF (OS_WINDOWS)
    CFLAGS(
        GLOBAL -DXML_STATIC
    )
ENDIF()

SRCS(
    lib/xmlparse.c
    lib/xmlrole.c
    lib/xmltok.c
)

END()
