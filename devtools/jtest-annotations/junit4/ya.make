JAVA_LIBRARY()


IF(JDK_VERSION == "")
    JDK_VERSION(11)
ENDIF()

JAVA_SRCS(SRCDIR src/main/java **/*)

END()
