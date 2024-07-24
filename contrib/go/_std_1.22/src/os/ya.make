GO_LIBRARY()
IF (OS_DARWIN AND ARCH_ARM64 AND RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_ARM64 AND RACE AND NOT CGO_ENABLED OR OS_DARWIN AND ARCH_ARM64 AND NOT RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_ARM64 AND NOT RACE AND NOT CGO_ENABLED OR OS_DARWIN AND ARCH_X86_64 AND RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_X86_64 AND RACE AND NOT CGO_ENABLED OR OS_DARWIN AND ARCH_X86_64 AND NOT RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_X86_64 AND NOT RACE AND NOT CGO_ENABLED)
    SRCS(
        dir.go
        dir_darwin.go
        endian_little.go
        env.go
        error.go
        error_errno.go
        error_posix.go
        exec.go
        exec_posix.go
        exec_unix.go
        executable.go
        executable_darwin.go
        file.go
        file_open_unix.go
        file_posix.go
        file_unix.go
        getwd.go
        path.go
        path_unix.go
        pipe_unix.go
        proc.go
        rawconn.go
        removeall_at.go
        stat.go
        stat_darwin.go
        stat_unix.go
        sticky_bsd.go
        sys.go
        sys_bsd.go
        sys_unix.go
        tempfile.go
        types.go
        types_unix.go
        wait_unimp.go
        zero_copy_stub.go
    )
ELSEIF (OS_LINUX AND ARCH_AARCH64 AND RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_AARCH64 AND RACE AND NOT CGO_ENABLED OR OS_LINUX AND ARCH_AARCH64 AND NOT RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_AARCH64 AND NOT RACE AND NOT CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND RACE AND NOT CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND NOT RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND NOT RACE AND NOT CGO_ENABLED)
    SRCS(
        dir.go
        dir_unix.go
        dirent_linux.go
        endian_little.go
        env.go
        error.go
        error_errno.go
        error_posix.go
        exec.go
        exec_posix.go
        exec_unix.go
        executable.go
        executable_procfs.go
        file.go
        file_open_unix.go
        file_posix.go
        file_unix.go
        getwd.go
        path.go
        path_unix.go
        pipe2_unix.go
        proc.go
        rawconn.go
        removeall_at.go
        stat.go
        stat_linux.go
        stat_unix.go
        sticky_notbsd.go
        sys.go
        sys_linux.go
        sys_unix.go
        tempfile.go
        types.go
        types_unix.go
        wait_waitid.go
        zero_copy_linux.go
    )
ELSEIF (OS_WINDOWS AND ARCH_X86_64 AND RACE AND CGO_ENABLED OR OS_WINDOWS AND ARCH_X86_64 AND RACE AND NOT CGO_ENABLED OR OS_WINDOWS AND ARCH_X86_64 AND NOT RACE AND CGO_ENABLED OR OS_WINDOWS AND ARCH_X86_64 AND NOT RACE AND NOT CGO_ENABLED)
    SRCS(
        dir.go
        dir_windows.go
        endian_little.go
        env.go
        error.go
        error_errno.go
        error_posix.go
        exec.go
        exec_posix.go
        exec_windows.go
        executable.go
        executable_windows.go
        file.go
        file_posix.go
        file_windows.go
        getwd.go
        path.go
        path_windows.go
        proc.go
        rawconn.go
        removeall_noat.go
        stat.go
        stat_windows.go
        sticky_notbsd.go
        sys.go
        sys_windows.go
        tempfile.go
        types.go
        types_windows.go
        zero_copy_stub.go
    )
ENDIF()
END()
