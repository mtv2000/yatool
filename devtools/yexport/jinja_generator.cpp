#include "jinja_generator.h"
#include "read_sem_graph.h"
#include "graph_visitor.h"
#include "attribute.h"

#include <devtools/ymake/compact_graph/query.h>
#include <devtools/ymake/common/uniq_vector.h>

#include <library/cpp/json/json_reader.h>
#include <library/cpp/resource/resource.h>

#include <util/generic/algorithm.h>
#include <util/generic/set.h>
#include <util/generic/yexception.h>
#include <util/generic/map.h>
#include <util/string/type.h>
#include <util/system/fs.h>

#include <contrib/libs/jinja2cpp/include/jinja2cpp/template.h>
#include <contrib/libs/jinja2cpp/include/jinja2cpp/template_env.h>

#include <fstream>
#include <vector>

namespace NYexport {

TJinjaProject::TJinjaProject() {
    SetFactoryTypes<TProjectSubdir, TJinjaTarget>();
}

TJinjaProject::TBuilder::TBuilder(TJinjaGenerator* generator, TAttrsPtr rootAttrs)
    : TProject::TBuilder(generator)
    , RootAttrs(rootAttrs)
    , Generator(generator)
{
    Project_ = MakeSimpleShared<TJinjaProject>();
}

static bool AddValueToJinjaList(jinja2::ValuesList& list, const jinja2::Value& value) {
    if (value.isList()) {
        // Never create list of lists, if value also list, concat all lists to one big list
        for (const auto& v: value.asList()) {
            list.emplace_back(v);
        }
    } else {
        list.emplace_back(value);
    }
    return true;
}

bool TJinjaProject::TBuilder::AddToTargetInducedAttr(const std::string& attrName, const jinja2::Value& value, const std::string& nodePath) {
    if (!CurTarget_) {
        spdlog::error("attempt to add target attribute '{}' while there is no active target at node {}", attrName, nodePath);
        return false;
    }
    auto& attrs = CurTarget_->Attrs->GetWritableMap();
    auto [listAttrIt, _] = attrs.emplace(attrName, jinja2::ValuesList{});
    auto& list = listAttrIt->second.asList();
    if (ValueInList(list, value)) {
        return true; // skip adding fully duplicate induced attributes
    }
    return AddValueToJinjaList(list, value);
}

void TJinjaProject::TBuilder::OnAttribute(const std::string& attribute) {
    Generator->OnAttribute(attribute);
}

void TJinjaProject::TBuilder::SetTestModDir(const std::string& testModDir) {
    CurTarget_.As<TJinjaTarget>()->TestModDir = testModDir;
}

const TNodeSemantics& TJinjaProject::TBuilder::ApplyReplacement(TPathView path, const TNodeSemantics& inputSem) const {
    return Generator->ApplyReplacement(path, inputSem);
}

bool TJinjaProject::TBuilder::ValueInList(const jinja2::ValuesList& list, const jinja2::Value& value) {
    if (list.empty()) {
        return false;
    }
    TStringBuilder valueStr;
    TStringBuilder listValueStr;
    Dump(valueStr.Out, value);
    for (const auto& listValue : list) {
        listValueStr.clear();
        Dump(listValueStr.Out, listValue);
        if (valueStr == listValueStr) {
            return true;
        }
    }
    return false;
}

void TJinjaProject::TBuilder::MergeTree(jinja2::ValuesMap& attrs, const jinja2::ValuesMap& tree) {
    for (auto& [attrName, attrValue]: tree) {
        if (attrValue.isMap()) {
            auto [attrIt, _] = attrs.emplace(attrName, jinja2::ValuesMap{});
            MergeTree(attrIt->second.asMap(), attrValue.asMap());
        } else {
            if (attrs.contains(attrName)) {
                spdlog::error("overwrite dict element {}", attrName);
            }
            attrs[attrName] = attrValue;
        }
    }
}

class TJinjaGeneratorVisitor: public TGraphVisitor {
public:
    TJinjaGeneratorVisitor(TJinjaGenerator* generator, TAttrsPtr rootAttrs, const TGeneratorSpec& generatorSpec)
        : TGraphVisitor(generator)
    {
        JinjaProjectBuilder_ = MakeSimpleShared<TJinjaProject::TBuilder>(generator, rootAttrs);
        ProjectBuilder_ = JinjaProjectBuilder_;

        if (const auto* tests = generatorSpec.Merge.FindPtr("test")) {
            for (const auto& item : *tests) {
                TestSubdirs_.push_back(item.c_str());
            }
        }
    }

    void OnTargetNodeSemantic(TState& state, const std::string& semName, const std::span<const std::string>& semArgs) override {
        bool isTestTarget = false;
        std::string modDir = semArgs[0].c_str();
        for (const auto& testSubdir: TestSubdirs_) {
            if (modDir != testSubdir && modDir.ends_with(testSubdir)) {
                modDir.resize(modDir.size() - testSubdir.size());
                isTestTarget = true;
                break;
            }
        }
        auto macroArgs = semArgs.subspan(2);
        state.Top().CurTargetHolder = ProjectBuilder_->CreateTarget(modDir);
        if (isTestTarget) {
            JinjaProjectBuilder_->SetTestModDir(modDir);
        }
        auto* curSubdir = ProjectBuilder_->CurrentSubdir();
        curSubdir->Attrs = Generator_->MakeAttrs(EAttrGroup::Directory, "dir " + curSubdir->Path.string());
        auto* curTarget = ProjectBuilder_->CurrentTarget();
        curTarget->Attrs = Generator_->MakeAttrs(EAttrGroup::Target, "target " + curTarget->Macro + " " + curTarget->Name);
        auto& attrs = curTarget->Attrs->GetWritableMap();
        curTarget->Name = semArgs[1];
        attrs.emplace("name", curTarget->Name);
        curTarget->Macro = semName;
        attrs.emplace("macro", curTarget->Macro);
        curTarget->MacroArgs = {macroArgs.begin(), macroArgs.end()};
        attrs.emplace("macroArgs", jinja2::ValuesList(curTarget->MacroArgs.begin(), curTarget->MacroArgs.end()));
        attrs.emplace("isTest", isTestTarget);
        const auto* jinjaTarget = dynamic_cast<const TJinjaTarget*>(JinjaProjectBuilder_->CurrentTarget());
        Mod2Target_.emplace(state.TopNode().Id(), jinjaTarget);
    }

    void OnNodeSemanticPostOrder(TState& state, const std::string& semName, ESemNameType semNameType, const std::span<const std::string>& semArgs) override {
        const TSemNodeData& data = state.TopNode().Value();
        if (semNameType == ESNT_RootAttr) {
            JinjaProjectBuilder_->SetRootAttr(semName, semArgs, data.Path);
        } else if (semNameType == ESNT_DirectoryAttr) {
            JinjaProjectBuilder_->SetDirectoryAttr(semName, semArgs, data.Path);
        } else if (semNameType == ESNT_TargetAttr) {
            JinjaProjectBuilder_->SetTargetAttr(semName, semArgs, data.Path);
        } else if (semNameType == ESNT_InducedAttr) {
            StoreInducedAttrValues(state.TopNode().Id(), semName, semArgs, data.Path);
        } else if (semNameType == ESNT_Unknown) {
            spdlog::error("Skip unknown semantic '{}' for file '{}'", semName, data.Path);
        }
    }

    void OnLeft(TState& state) override {
        const auto& dep = state.Top().CurDep();
        if (IsDirectPeerdirDep(dep)) {
            //Note: This part checks dependence of the test on the library in the same dir, because for java we should not distribute attributes
            bool isSameDir = false;
            const auto* toTarget = Mod2Target_[dep.To().Id()];
            if (auto* curSubdir = ProjectBuilder_->CurrentSubdir(); curSubdir) {
                for (const auto& target: curSubdir->Targets) {
                    if (target.Get() == toTarget) {
                        isSameDir = true;
                        break;
                    }
                }
            }
            const auto libIt = InducedAttrs_.find(dep.To().Id());
            if (!isSameDir && libIt != InducedAttrs_.end()) {
                const TSemNodeData& data = dep.To().Value();
/*
    Generating induced attributes and excludes< for example, project is

    prog --> lib1 with excluding ex1
         \-> lib2 with excluding ex2

    And toml is:

    [attrs.induced]
    consumer-classpath="str"
    consumer-jar="str"

    For prog must be attributes map:
    ...
    consumer: [
        {
            classpath: "lib1",
            jar: "lib1.jar",
            excludes: {
                consumer: [
                    {
                        classpath: "ex1",
                        jar: "ex1.jar",
                    }
                ],
            },
        },
        {
            classpath: "lib2",
            jar: "lib2.jar",
            excludes: {
                consumer: [
                    {
                        classpath: "ex2",
                        jar: "ex2.jar",
                    }
                ],
            },
        },
    ]
    ...
*/
                // Make excludes map for each induced library
                jinja2::ValuesMap excludes;
                // Extract excludes node ids from current dependence
                if (const TSemDepData* depData = reinterpret_cast<const TSemGraph&>(dep.Graph()).GetDepData(dep); depData) {
                    if (const auto excludesIt = depData->find(DEPATTR_EXCLUDES); excludesIt != depData->end()) {
                        TVector<TNodeId> excludeNodeIds;
                        TVector<TNodeId> excludeNodeIdsWOInduced;
                        Y_ASSERT(excludesIt->second.isList());
                        // Collect all excluded node ids and collect ids without induced attributes
                        for (const auto& excludeNodeVal : excludesIt->second.asList()) {
                            const auto excludeNodeId = static_cast<TNodeId>(excludeNodeVal.get<int64_t>());
                            excludeNodeIds.emplace_back(excludeNodeId);
                            if (!InducedAttrs_.contains(excludeNodeId)) {
                                excludeNodeIdsWOInduced.emplace_back(excludeNodeId);
                            }
                        }
                        if (!excludeNodeIdsWOInduced.empty()) { // visit all not visited exclude nodes for make induced attributes
                            IterateAll(reinterpret_cast<const TSemGraph&>(dep.Graph()), excludeNodeIdsWOInduced, *this);
                        }
                        // for each excluded node id get all it induced attrs
                        for (auto excludeNodeId : excludeNodeIds) {
                            const auto excludeIt = InducedAttrs_.find(excludeNodeId);
                            if (excludeIt != InducedAttrs_.end()) {
                                // Put all induced attrs of excluded library to lists by induced attribute name
                                for (const auto& [attrName, value] : excludeIt->second->GetMap()) {
                                    auto [listIt, _] = excludes.emplace(attrName, jinja2::ValuesList{});
                                    AddValueToJinjaList(listIt->second.asList(), value);
                                }
                            } else {
                                spdlog::error("Not found induced for excluded node id {} at {}", excludeNodeId, data.Path);
                            }
                        }
                    }
                }
                const auto fromTarget = Mod2Target_[dep.From().Id()];
                bool isTestDep = fromTarget && toTarget && toTarget->IsTest();
                for (const auto& [attrName, value] : libIt->second->GetMap()) {
                    if (value.isMap() && (!excludes.empty() || isTestDep)) {
                        // For each induced attribute in map format add submap with excludes
                        jinja2::ValuesMap valueWithDepAttrs = value.asMap();
                        if (!excludes.empty()) {
                            valueWithDepAttrs.emplace(TJinjaGenerator::EXCLUDES_ATTR, excludes);
                        }
                        if (isTestDep) {
                            valueWithDepAttrs.emplace(TJinjaGenerator::TESTDEP_ATTR, toTarget->TestModDir);
                        }
                        JinjaProjectBuilder_->AddToTargetInducedAttr(attrName, valueWithDepAttrs, data.Path);
                    } else {
                        JinjaProjectBuilder_->AddToTargetInducedAttr(attrName, value, data.Path);
                    }
                }
            }
        }
    }

private:
    template<IterableValues Values>
    void StoreInducedAttrValues(TNodeId nodeId, const std::string& attrName, const Values& values, const std::string& nodePath) {
        auto nodeIt = InducedAttrs_.find(nodeId);
        if (nodeIt == InducedAttrs_.end()) {
            auto [emplaceNodeIt, _] = InducedAttrs_.emplace(nodeId, Generator_->MakeAttrs(EAttrGroup::Induced, "induced by " + std::to_string(nodeId)));
            nodeIt = emplaceNodeIt;
        }
        nodeIt->second->SetAttrValue(attrName, values, nodePath);
    }

    TSimpleSharedPtr<TJinjaProject::TBuilder> JinjaProjectBuilder_;

    THashMap<TNodeId, const TJinjaTarget*> Mod2Target_;
    THashMap<TNodeId, TAttrsPtr> InducedAttrs_;
    TVector<std::string> TestSubdirs_;
};

THolder<TJinjaGenerator> TJinjaGenerator::Load(
    const fs::path& arcadiaRoot,
    const std::string& generator,
    const fs::path& configDir,
    const std::optional<TDumpOpts> dumpOpts,
    const std::optional<TDebugOpts> debugOpts
) {
    const auto generatorDir = arcadiaRoot / GENERATORS_ROOT / generator;
    const auto generatorFile = generatorDir / GENERATOR_FILE;
    if (!fs::exists(generatorFile)) {
        YEXPORT_THROW(fmt::format("Failed to load generator {}. No {} file found", generator, generatorFile.c_str()));
    }
    THolder<TJinjaGenerator> result = MakeHolder<TJinjaGenerator>();
    if (dumpOpts.has_value()) {
        result->DumpOpts_ = dumpOpts.value();
    }
    if (debugOpts.has_value()) {
        result->DebugOpts_ = debugOpts.value();
    }

    auto& generatorSpec = result->GeneratorSpec = ReadGeneratorSpec(generatorFile);

    result->YexportSpec = result->ReadYexportSpec(configDir);
    result->GeneratorDir = generatorDir;
    result->ArcadiaRoot = arcadiaRoot;
    result->SetupJinjaEnv();

    result->RootTemplates = result->LoadJinjaTemplates(generatorSpec.Root.Templates);
    result->DirTemplates = result->LoadJinjaTemplates(generatorSpec.Dir.Templates);
    result->CommonTemplates = result->LoadJinjaTemplates(generatorSpec.Common.Templates);

    if (result->GeneratorSpec.Targets.empty()) {
        std::string message = "[error] No targets exist in the generator file: ";
        throw TBadGeneratorSpec(message.append(generatorFile));
    }

    for (const auto& [targetName, target]: generatorSpec.Targets) {
        result->TargetTemplates[targetName] = result->LoadJinjaTemplates(target.Templates);
    }

    result->RootAttrs = result->MakeAttrs(EAttrGroup::Root, "root");

    return result;
}

void TJinjaGenerator::AnalizeSemGraph(const TVector<TNodeId>& startDirs, const TSemGraph& graph) {
    TJinjaGeneratorVisitor visitor(this, RootAttrs, GeneratorSpec);
    IterateAll(graph, startDirs, visitor);
    Project = visitor.TakeFinalizedProject();
}

void TJinjaGenerator::LoadSemGraph(const std::string&, const fs::path& semGraph) {
    const auto [graph, startDirs] = ReadSemGraph(semGraph, GeneratorSpec.UseManagedPeersClosure);
    AnalizeSemGraph(startDirs, *graph);
}

EAttrTypes TJinjaGenerator::GetAttrType(EAttrGroup attrGroup, const std::string_view attrName) const {
    if (const auto* attrs = GeneratorSpec.AttrGroups.FindPtr(attrGroup)) {
        if (const auto it = attrs->find(attrName); it != attrs->end()) {
            return it->second;
        }
    }
    return EAttrTypes::Unknown;
}

/// Get dump of attributes tree with values for testing or debug
void TJinjaGenerator::DumpSems(IOutputStream& out) {
    if (DumpOpts_.DumpPathPrefixes.empty()) {
        out << "--- ROOT\n" << Project->SemsDump;
    }
    for (const auto& subdir: Project->GetSubdirs()) {
        if (subdir->Targets.empty()) {
            continue;
        }
        const std::string path = subdir->Path;
        if (!DumpOpts_.DumpPathPrefixes.empty()) {
            bool dumpIt = false;
            for (const auto& prefix : DumpOpts_.DumpPathPrefixes) {
                if (path.substr(0, prefix.size()) == prefix) {
                    dumpIt = true;
                    break;
                }
            }
            if (!dumpIt) {
                continue;
            }
        }
        out << "--- DIR " << path << "\n";
        for (const auto& target: subdir->Targets) {
            out << "--- TARGET " << target->Name << "\n" << target->SemsDump;
        }
    }
}

/// Get dump of attributes tree with values for testing or debug
void TJinjaGenerator::DumpAttrs(IOutputStream& out) {
    ::NYexport::Dump(out, FinalizeAttrsForDump());
}

void TJinjaGenerator::Render(ECleanIgnored) {
    YEXPORT_VERIFY(Project, "Cannot render because project was not yet loaded");
    CopyFilesAndResources();
    FinalizeSubdirsAttrs();
    for (const auto& subdir: Project->GetSubdirs()) {
        if (subdir->Targets.empty()) {
            continue;
        }
        RenderSubdir(subdir);
    }

    FinalizeRootAttrs();
    RenderJinjaTemplates(RootAttrs, RootTemplates);
}

void TJinjaGenerator::RenderSubdir(TProjectSubdirPtr subdir) {
    SetCurrentDirectory(ArcadiaRoot / subdir->Path);
    for (const auto& [targetName, targetNameAttrs] : subdir->Attrs->GetMap()) {
        // TODO vvv Store attributes in TAttrs
        TAttrsPtr targetAttrsStorage = MakeAttrs(EAttrGroup::Target, targetName);
        targetAttrsStorage->GetWritableMap() = targetNameAttrs.asMap();
        // TODO ^^^ Store attributes in TAttrs
        RenderJinjaTemplates(targetAttrsStorage, TargetTemplates[targetName], subdir->Path);
    }
}

const jinja2::ValuesMap& TJinjaGenerator::FinalizeRootAttrs() {
    YEXPORT_VERIFY(Project, "Cannot finalize root attrs because project was not yet loaded");
    if (!RootAttrs) {
        RootAttrs = MakeAttrs(EAttrGroup::Root, "root");
    }
    auto& attrs = RootAttrs->GetWritableMap();
    if (attrs.contains("projectName")) { // already finalized
        return attrs;
    }
    auto [subdirsIt, subdirsInserted] = attrs.emplace("subdirs", jinja2::ValuesList{});
    for (const auto& subdir: Project->GetSubdirs()) {
        if (subdir->Targets.empty()) {
            continue;
        }
        subdirsIt->second.asList().emplace_back(subdir->Path.c_str());
    }
    attrs.emplace("arcadiaRoot", ArcadiaRoot);
    if (ExportFileManager) {
        attrs.emplace("exportRoot", ExportFileManager->GetExportRoot());
    }
    attrs.emplace("projectName", ProjectName);
    if (!YexportSpec.AddAttrsDir.empty()) {
        attrs.emplace("add_attrs_dir", YexportSpec.AddAttrsDir);
    }
    if (!YexportSpec.AddAttrsTarget.empty()) {
        attrs.emplace("add_attrs_target", YexportSpec.AddAttrsTarget);
    }
    if (DebugOpts_.DebugAttrs) {
        attrs.emplace(DEBUG_ATTRS_ATTR, ::NYexport::Dump(RootAttrs->GetMap()));
    }
    if (DebugOpts_.DebugSems) {
        attrs.emplace(DEBUG_SEMS_ATTR, Project->SemsDump);
    }
    return RootAttrs->GetMap();
}

jinja2::ValuesMap TJinjaGenerator::FinalizeSubdirsAttrs(const std::vector<std::string>& pathPrefixes) {
    YEXPORT_VERIFY(Project, "Cannot finalize subdirs attrs because project was not yet loaded");
    jinja2::ValuesMap subdirsAttrs;
    for (auto& subdir: Project->GetSubdirs()) {
        if (subdir->Targets.empty()) {
            continue;
        }
        if (!pathPrefixes.empty()) {
            const std::string path = subdir->Path;
            bool finalizeIt = false;
            for (const auto& prefix : pathPrefixes) {
                if (path.substr(0, prefix.size()) == prefix) {
                    finalizeIt = true;
                    break;
                }
            }
            if (!finalizeIt) {
                continue;
            }
        }
        auto& subdirAttrs = subdir->Attrs->GetWritableMap();
        std::map<std::string, std::string> semsDumps;
        for (auto target: subdir->Targets) {
            auto& targetAttrs = target->Attrs->GetWritableMap();
            if (!YexportSpec.AddAttrsTarget.empty()) {
                TJinjaProject::TBuilder::MergeTree(targetAttrs, YexportSpec.AddAttrsTarget);
            }

            auto targetMacroAttrsIt = subdirAttrs.find(target->Macro);
            if (targetMacroAttrsIt == subdirAttrs.end()) {
                jinja2::ValuesMap defaultTargetNameAttrs;
                defaultTargetNameAttrs.emplace("arcadiaRoot", ArcadiaRoot);
                if (ExportFileManager) {
                    defaultTargetNameAttrs.emplace("exportRoot", ExportFileManager->GetExportRoot());
                }
                defaultTargetNameAttrs.emplace("hasTest", false);
                defaultTargetNameAttrs.emplace("extra_targets", jinja2::ValuesList{});
                if (!YexportSpec.AddAttrsDir.empty()) {
                    TJinjaProject::TBuilder::MergeTree(defaultTargetNameAttrs, YexportSpec.AddAttrsDir);
                }
                targetMacroAttrsIt = subdirAttrs.emplace(target->Macro, std::move(defaultTargetNameAttrs)).first;
                if (DumpOpts_.DumpSems || DebugOpts_.DebugSems) {
                    semsDumps.emplace(target->Macro, target->SemsDump);
                }
            }
            auto& targetMacroAttrs = targetMacroAttrsIt->second.asMap();
            auto isTest = target.As<TJinjaTarget>()->IsTest();
            if (isTest) {
                targetMacroAttrs.insert_or_assign("hasTest", true);
            }
            if (isTest) {
                auto& extra_targets = targetMacroAttrs["extra_targets"].asList();
                extra_targets.emplace_back(targetAttrs);
            } else {
                auto [targetIt, inserted] = targetMacroAttrs.insert_or_assign("target", targetAttrs);
                if (!inserted) {
                    spdlog::error("Main target {} overwrote by {}", targetIt->second.asMap()["name"].asString(), targetAttrs["name"].asString());
                }
            }
        }
        if (DebugOpts_.DebugAttrs) {
            for (auto& [targetName, targetNameAttrs] : subdirAttrs) {
                targetNameAttrs.asMap().emplace(DEBUG_ATTRS_ATTR, ::NYexport::Dump(targetNameAttrs));
            }
        }
        if (DebugOpts_.DebugSems) {
            for (auto& [targetName, semsDump] : semsDumps) {
                subdirAttrs[targetName].asMap().emplace(DEBUG_SEMS_ATTR, semsDump);
            }
        }
        subdirsAttrs.emplace(subdir->Path.c_str(), subdirAttrs);
    }
    return subdirsAttrs;
}

jinja2::ValuesMap TJinjaGenerator::FinalizeAttrsForDump() {
    // disable creating debug template attributes
    DebugOpts_.DebugSems = false;
    DebugOpts_.DebugAttrs = false;
    jinja2::ValuesMap allAttrs;
    allAttrs.emplace("root", FinalizeRootAttrs());
    allAttrs.emplace("subdirs", FinalizeSubdirsAttrs(DumpOpts_.DumpPathPrefixes));
    return allAttrs;
}

THashMap<fs::path, TVector<TJinjaTarget>> TJinjaGenerator::GetSubdirsTargets() const {
    YEXPORT_VERIFY(Project, "Cannot get subdirs table because project was not yet loaded");
    THashMap<fs::path, TVector<TJinjaTarget>> res;
    for (const auto& subdir: Project->GetSubdirs()) {
        TVector<TJinjaTarget> targets;
        Transform(subdir->Targets.begin(), subdir->Targets.end(), std::back_inserter(targets), [&](TProjectTargetPtr target) { return *target.As<TJinjaTarget>(); });
        res.emplace(subdir->Path, targets);
    }
    return res;
}

void TJinjaGenerator::SetSpec(const TGeneratorSpec& spec) {
    GeneratorSpec = spec;
    if (!RootAttrs) {
        RootAttrs = MakeAttrs(EAttrGroup::Root, "root");
    }
};

}
