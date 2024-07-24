GO_LIBRARY()
IF (OS_DARWIN AND ARCH_ARM64 AND RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_ARM64 AND RACE AND NOT CGO_ENABLED OR OS_DARWIN AND ARCH_ARM64 AND NOT RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_ARM64 AND NOT RACE AND NOT CGO_ENABLED OR OS_LINUX AND ARCH_AARCH64 AND RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_AARCH64 AND RACE AND NOT CGO_ENABLED OR OS_LINUX AND ARCH_AARCH64 AND NOT RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_AARCH64 AND NOT RACE AND NOT CGO_ENABLED)
    SRCS(
        abs.go
        acosh.go
        asin.go
        asinh.go
        atan.go
        atan2.go
        atanh.go
        bits.go
        cbrt.go
        const.go
        copysign.go
        dim.go
        dim_arm64.s
        dim_asm.go
        erf.go
        erfinv.go
        exp.go
        exp2_asm.go
        exp_arm64.s
        exp_asm.go
        expm1.go
        floor.go
        floor_arm64.s
        floor_asm.go
        fma.go
        frexp.go
        gamma.go
        hypot.go
        hypot_noasm.go
        j0.go
        j1.go
        jn.go
        ldexp.go
        lgamma.go
        log.go
        log10.go
        log1p.go
        log_stub.go
        logb.go
        mod.go
        modf.go
        modf_arm64.s
        modf_asm.go
        nextafter.go
        pow.go
        pow10.go
        remainder.go
        signbit.go
        sin.go
        sincos.go
        sinh.go
        sqrt.go
        stubs.go
        tan.go
        tanh.go
        trig_reduce.go
        unsafe.go
    )
ELSEIF (OS_DARWIN AND ARCH_X86_64 AND RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_X86_64 AND RACE AND NOT CGO_ENABLED OR OS_DARWIN AND ARCH_X86_64 AND NOT RACE AND CGO_ENABLED OR OS_DARWIN AND ARCH_X86_64 AND NOT RACE AND NOT CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND RACE AND NOT CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND NOT RACE AND CGO_ENABLED OR OS_LINUX AND ARCH_X86_64 AND NOT RACE AND NOT CGO_ENABLED OR OS_WINDOWS AND ARCH_X86_64 AND RACE AND CGO_ENABLED OR OS_WINDOWS AND ARCH_X86_64 AND RACE AND NOT CGO_ENABLED OR OS_WINDOWS AND ARCH_X86_64 AND NOT RACE AND CGO_ENABLED OR OS_WINDOWS AND ARCH_X86_64 AND NOT RACE AND NOT CGO_ENABLED)
    SRCS(
        abs.go
        acosh.go
        asin.go
        asinh.go
        atan.go
        atan2.go
        atanh.go
        bits.go
        cbrt.go
        const.go
        copysign.go
        dim.go
        dim_amd64.s
        dim_asm.go
        erf.go
        erfinv.go
        exp.go
        exp2_noasm.go
        exp_amd64.go
        exp_amd64.s
        exp_asm.go
        expm1.go
        floor.go
        floor_amd64.s
        floor_asm.go
        fma.go
        frexp.go
        gamma.go
        hypot.go
        hypot_amd64.s
        hypot_asm.go
        j0.go
        j1.go
        jn.go
        ldexp.go
        lgamma.go
        log.go
        log10.go
        log1p.go
        log_amd64.s
        log_asm.go
        logb.go
        mod.go
        modf.go
        modf_noasm.go
        nextafter.go
        pow.go
        pow10.go
        remainder.go
        signbit.go
        sin.go
        sincos.go
        sinh.go
        sqrt.go
        stubs.go
        tan.go
        tanh.go
        trig_reduce.go
        unsafe.go
    )
ENDIF()
END()
