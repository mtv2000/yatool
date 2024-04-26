#pragma once

#include "exec.h"
#include "vars.h"

#include <devtools/ymake/compact_graph/dep_graph.h>
#include <devtools/ymake/make_plan/make_plan.h>

#include <util/generic/fwd.h>
#include <util/generic/string.h>
#include <util/system/types.h>

class TYMake;
class TModule;
class TModules;
class TJSONVisitor;
struct TCommandInfo;
struct TMacroData;
struct TDumpInfoUID;

class TJsonCmdAcceptor: private TMultiCmdDescr, private TCommandSequenceWriterStubs {
public:
    TMultiCmdDescr* GetAcceptor() noexcept { return this; }
protected:
    virtual void OnCmdFinished(const TVector<TSingleCmd>& commands, TCommandInfo& cmdInfo, const TVars& vars) = 0;

private:
    void Start(const TStringBuf& cmd, TString& res) override;
    void ConvertText(TString& res, const TStringBuf& text) override;
    void ConvertMacro(TString& res, TMacroData& macro) override;
    void StartCommand(TString& res) override;
    void FinishCommand(TString& res) override;
    void Finish(TString& res, TCommandInfo& cmdInfo, const TVars& vars) override;

    ICommandSequenceWriter* Upgrade() override { return this; }

private:
    void BeginScript() override;
    void BeginCommand() override;
    void WriteArgument(TStringBuf arg) override;
    void WriteEnv(TStringBuf env) override;
    void EndCommand() override;
    void EndScript(TCommandInfo& cmdInfo, const TVars& vars) override;

private:
    void FinishToken(TString& res, const char* at, bool nextIsMacro);

private:
    TStringBuf InCmd;
    size_t TokenStart; // offset in InCmd
    char TopQuote;
};

class TSubst2Json: public TJsonCmdAcceptor {
    // data
    TDumpInfoUID& DumpInfo;
    TKeyValueMap<TString> TargetProperties;
    const TJSONVisitor& JSONVisitor;

    bool IsFake = false;
    TMakeNode* MakeNode = nullptr;

public:
    TSubst2Json(const TJSONVisitor&, TDumpInfoUID&, TMakeNode* makeNode);

    void GenerateJsonTargetProperties(const TConstDepNodeRef&, const TModule* mod, bool isGlobalNode);

    // For node refresh in case of partial rendering
    void FakeFinish(TCommandInfo& cmdInfo);
    void CmdFinished(const TVector<TSingleCmd>& commands, TCommandInfo& cmdInfo, const TVars& vars);

    void UpdateInputs();

private:
    // TJsonCmdAcceptor implementation.
    void OnCmdFinished(const TVector<TSingleCmd>& commands, TCommandInfo& cmdInfo, const TVars& vars) override;
};
