RESOURCES_LIBRARY()
SET(SCRIPTGEN_LINUX sbr:4351926887)
SET(SCRIPTGEN_LINUX_AARCH64 sbr:4351922617)
SET(SCRIPTGEN_DARWIN_ARM64 sbr:4351924553)
SET(SCRIPTGEN_DARWIN sbr:4351925664)
SET(SCRIPTGEN_WIN32 sbr:4351923493)

DECLARE_EXTERNAL_HOST_RESOURCES_BUNDLE(
    SCRIPTGEN
    ${SCRIPTGEN_LINUX} FOR LINUX
    ${SCRIPTGEN_LINUX_AARCH64} FOR LINUX-AARCH64
    ${SCRIPTGEN_DARWIN} FOR DARWIN
    ${SCRIPTGEN_DARWIN_ARM64} FOR DARWIN-ARM64
    ${SCRIPTGEN_WIN32} FOR WIN32
)

IF(OS_DARWIN AND ARCH_ARM64)
    DECLARE_EXTERNAL_RESOURCE(WITH_SCRIPTGEN ${SCRIPTGEN_DARWIN_ARM64})
ELSEIF(OS_DARWIN AND ARCH_X86_64)
    DECLARE_EXTERNAL_RESOURCE(WITH_SCRIPTGEN ${SCRIPTGEN_DARWIN})
ELSEIF(OS_LINUX AND ARCH_X86_64)
    DECLARE_EXTERNAL_RESOURCE(WITH_SCRIPTGEN ${SCRIPTGEN_LINUX})
ELSEIF(OS_LINUX AND ARCH_AARCH64)
    DECLARE_EXTERNAL_RESOURCE(WITH_SCRIPTGEN ${SCRIPTGEN_LINUX_AARCH64})
ELSEIF(OS_WINDOWS)
    DECLARE_EXTERNAL_RESOURCE(WITH_SCRIPTGEN ${SCRIPTGEN_WIN32})
ENDIF()

END()
