#pragma once

#include "generator_spec.h"
#include "yexport_generator.h"
#include "std_helpers.h"
#include "target_replacements.h"
#include "jinja_helpers.h"
#include "dump.h"
#include "debug.h"

#include <util/generic/hash_set.h>

#include <filesystem>
#include <string>
#include <type_traits>

namespace NYexport {

/// Common base class for generators configurable with generator.toml specs
class TSpecBasedGenerator : public TYexportGenerator {
public:
    TSpecBasedGenerator() noexcept = default;
    virtual ~TSpecBasedGenerator() = default;

    const TGeneratorSpec& GetGeneratorSpec() const;
    const fs::path& GetGeneratorDir() const;
    const TNodeSemantics& ApplyReplacement(TPathView path, const TNodeSemantics& inputSem) const;
    void ApplyRules(TTargetAttributes& map) const;
    jinja2::TemplateEnv* GetJinjaEnv() const;
    void SetCurrentDirectory(const fs::path& dir) const;

    void SetupJinjaEnv();
    void OnAttribute(const TAttribute& attribute);
    void OnPlatform(const std::string_view& platform);

    const TDumpOpts& DumpOpts() const {
        return DumpOpts_;
    }
    const TDebugOpts& DebugOpts() const {
        return DebugOpts_;
    }

    static constexpr const char* GENERATOR_FILE = "generator.toml";
    static constexpr const char* GENERATORS_ROOT = "build/export_generators";
    static constexpr const char* GENERATOR_TEMPLATES_PREFIX = "[generator]/";
    static constexpr const char* YEXPORT_FILE = "yexport.toml";
    static constexpr const char* DEBUG_SEMS_ATTR = "dump_sems";
    static constexpr const char* DEBUG_ATTRS_ATTR = "dump_attrs";

protected:
    void CopyFilesAndResources();

    using TJinjaFileSystemPtr = std::shared_ptr<jinja2::RealFileSystem>;
    using TJinjaEnvPtr = std::unique_ptr<jinja2::TemplateEnv>;

    fs::path GeneratorDir;
    fs::path ArcadiaRoot;

    TGeneratorSpec GeneratorSpec;
    TYexportSpec YexportSpec;
    THashSet<std::string> UsedAttributes;
    THashSet<const TGeneratorRule*> UsedRules;
    TTargetReplacements TargetReplacements_;///< Patches for semantics by path
    TDumpOpts DumpOpts_;///< Dump options for semantics and template attributes
    TDebugOpts DebugOpts_;///< Debug options for semantics and template attributes

    TYexportSpec ReadYexportSpec(fs::path configDir = "");

private:
    TJinjaFileSystemPtr SourceTemplateFs;
    TJinjaEnvPtr JinjaEnv;

    fs::path PathByCopyLocation(ECopyLocation location) const;
    TCopySpec CollectFilesToCopy() const;
};

}
