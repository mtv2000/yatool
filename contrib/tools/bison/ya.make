# Generated by devtools/yamaker from nixpkgs 22.11.

PROGRAM(bison)

LICENSE(
    Bison-exception-2.2 AND
    GPL-3.0-only AND
    GPL-3.0-or-later AND
    GPL-3.0-or-later WITH Bison-exception-2.2
)

LICENSE_TEXTS(.yandex_meta/licenses.list.txt)

VERSION(3.5.4)

ORIGINAL_SOURCE(mirror://gnu/bison/bison-3.5.4.tar.gz)

PEERDIR(
    contrib/tools/bison/lib
)

ADDINCL(
    contrib/tools/bison
    contrib/tools/bison/lib
)

NO_COMPILER_WARNINGS()

NO_RUNTIME()

CFLAGS(
    -DEXEEXT=\"\"
    -DINSTALLDIR=\"/var/empty/bison-3.5.4/bin\"
)

SRCS(
    src/AnnotationList.c
    src/InadequacyList.c
    src/Sbitset.c
    src/assoc.c
    src/closure.c
    src/complain.c
    src/conflicts.c
    src/derives.c
    src/files.c
    src/fixits.c
    src/getargs.c
    src/gram.c
    src/graphviz.c
    src/ielr.c
    src/lalr.c
    src/location.c
    src/lr0.c
    src/main.c
    src/muscle-tab.c
    src/named-ref.c
    src/nullable.c
    src/output.c
    src/parse-gram.c
    src/print-graph.c
    src/print-xml.c
    src/print.c
    src/reader.c
    src/reduce.c
    src/relation.c
    src/scan-code-c.c
    src/scan-gram-c.c
    src/scan-skel-c.c
    src/state.c
    src/symlist.c
    src/symtab.c
    src/tables.c
    src/uniqstr.c
)

END()

RECURSE(
    lib
)
