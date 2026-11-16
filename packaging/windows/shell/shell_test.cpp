// Exercises parrotia_shell.dll the way Explorer does, without installing it.
// Usage: shell_test.exe <parrotia_shell.dll> <empty scratch folder>
// Exit code 0 means every check passed. Run by packaging/windows/msix.py.

#include <windows.h>
#include <appmodel.h>
#include <shlobj_core.h>
#include <shobjidl_core.h>
#include <wrl/client.h>

#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "shell_config.h"

using Microsoft::WRL::ComPtr;

namespace {

int failures = 0;

void Check(bool condition, const char* what) {
    std::printf("%s: %s\n", condition ? "ok" : "FAIL", what);
    if (!condition) ++failures;
}

std::wstring Touch(const std::wstring& folder, const std::wstring& name) {
    std::wstring path = folder + L"\\" + name;
    HANDLE handle = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                                FILE_ATTRIBUTE_NORMAL, nullptr);
    CloseHandle(handle);
    return path;
}

ComPtr<IShellItemArray> Selection(const std::vector<std::wstring>& paths) {
    std::vector<PIDLIST_ABSOLUTE> ids;
    for (const auto& path : paths) {
        PIDLIST_ABSOLUTE id = nullptr;
        if (SUCCEEDED(SHParseDisplayName(path.c_str(), nullptr, &id, 0, nullptr))) ids.push_back(id);
    }
    ComPtr<IShellItemArray> items;
    SHCreateShellItemArrayFromIDLists(static_cast<UINT>(ids.size()),
                                      const_cast<PCIDLIST_ABSOLUTE_ARRAY>(ids.data()), &items);
    for (auto id : ids) CoTaskMemFree(id);
    return items;
}

std::wstring Quoted(const std::wstring& path) { return L"\"" + path + L"\""; }

// What the DLL starts: the package's AppUserModelID when it is installed
// (its folder is named after the package full name), else the executable.
std::wstring Target(const std::wstring& dllFolder) {
    std::wstring fullName = dllFolder.substr(dllFolder.find_last_of(L'\\') + 1);
    UINT32 length = PACKAGE_FAMILY_NAME_MAX_LENGTH + 1;
    std::wstring family(length, L'\0');
    if (PackageFamilyNameFromFullName(fullName.c_str(), &length, family.data()) == ERROR_SUCCESS) {
        family.resize(length - 1);
        std::printf("mode: installed package, activates %ls!%ls\n", family.c_str(), kApplicationId);
        return family + L"!" + kApplicationId;
    }
    std::printf("mode: unpackaged DLL, starts the executable beside it\n");
    return Quoted(dllFolder + L"\\" + kExecutable);
}

// The shell reports long names; %TEMP% may hold an 8.3 short name.
std::wstring LongPath(const std::wstring& path) {
    DWORD size = GetLongPathNameW(path.c_str(), nullptr, 0);
    if (size == 0) return path;
    std::wstring full(size, L'\0');
    full.resize(GetLongPathNameW(path.c_str(), full.data(), size));
    return full;
}

std::vector<std::wstring> ReadLines(const std::wstring& file) {
    std::ifstream stream(file, std::ios::binary);
    std::string content((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
    std::vector<std::wstring> lines;
    size_t start = 0;
    while (start < content.size()) {
        size_t end = content.find('\n', start);
        std::string line = content.substr(start, end - start);
        int size = MultiByteToWideChar(CP_UTF8, 0, line.c_str(), static_cast<int>(line.size()), nullptr, 0);
        std::wstring wide(static_cast<size_t>(size), L'\0');
        MultiByteToWideChar(CP_UTF8, 0, line.c_str(), static_cast<int>(line.size()), wide.data(), size);
        lines.push_back(wide);
        if (end == std::string::npos) break;
        start = end + 1;
    }
    return lines;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) {
        std::printf("usage: shell_test <dll> <scratch folder>\n");
        return 2;
    }
    std::wstring dll = LongPath(argv[1]);
    std::wstring folder = LongPath(argv[2]);
    std::wstring dllFolder = dll.substr(0, dll.find_last_of(L'\\'));
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

    HMODULE module = LoadLibraryW(dll.c_str());
    Check(module != nullptr, "DLL loads");
    if (module == nullptr) return 1;
    using GetClassObject = HRESULT(STDAPICALLTYPE*)(REFCLSID, REFIID, void**);
    auto getClassObject = reinterpret_cast<GetClassObject>(GetProcAddress(module, "DllGetClassObject"));
    Check(getClassObject != nullptr && GetProcAddress(module, "DllCanUnloadNow") != nullptr,
          "COM entry points are exported");
    CLSID clsid;
    CLSIDFromString(L"{" PARROTIA_SHELL_CLSID L"}", &clsid);
    ComPtr<IClassFactory> factory;
    ComPtr<IExplorerCommand> command;
    if (getClassObject) getClassObject(clsid, IID_PPV_ARGS(&factory));
    if (factory) factory->CreateInstance(nullptr, IID_PPV_ARGS(&command));
    Check(command != nullptr, "IExplorerCommand is created from the manifest CLSID");
    if (!command) return 1;

    std::wstring audio = Touch(folder, L"talk.mp3");
    std::wstring text = Touch(folder, L"notes.txt");
    std::wstring video = Touch(folder, L"Reunião final.MP4");

    PWSTR title = nullptr;
    command->GetTitle(nullptr, &title);
    Check(title && std::wstring(title) == kTitle, "title");
    CoTaskMemFree(title);

    PWSTR icon = nullptr;
    command->GetIcon(nullptr, &icon);
    Check(icon && std::wstring(icon) == dllFolder + L"\\" + kExecutable + L",0", "icon is the app executable");
    CoTaskMemFree(icon);

    EXPCMDSTATE state = ECS_ENABLED;
    command->GetState(Selection({text}).Get(), TRUE, &state);
    Check(state == ECS_HIDDEN, "hidden when no supported media is selected");
    command->GetState(Selection({text, audio}).Get(), TRUE, &state);
    Check(state == ECS_ENABLED, "shown when supported media is selected");

    std::wstring record = folder + L"\\dry-run.txt";
    SetEnvironmentVariableW(L"PARROTIA_SHELL_DRY_RUN", record.c_str());
    command->Invoke(Selection({audio, text, video}).Get(), nullptr);
    std::wstring expected = Target(dllFolder) + L" --shell " + Quoted(audio) +
                            L" " + Quoted(video);
    std::vector<std::wstring> lines = ReadLines(record);
    Check(lines.size() == 1 && lines[0] == expected, "invoke passes only supported files, quoted");

    // A selection longer than one command line is split across processes.
    DeleteFileW(record.c_str());
    std::vector<std::wstring> many;
    for (int i = 0; i < 300; ++i) {
        many.push_back(Touch(folder, L"recording-" + std::wstring(100, L'x') + std::to_wstring(i) + L".wav"));
    }
    command->Invoke(Selection(many).Get(), nullptr);
    lines = ReadLines(record);
    size_t passed = 0;
    bool fits = true;
    for (const auto& line : lines) {
        fits = fits && line.size() < 32767;
        for (const auto& path : many) {
            if (line.find(Quoted(path)) != std::wstring::npos) ++passed;
        }
    }
    Check(lines.size() > 1 && fits && passed == many.size(), "long selections are split, nothing lost");

    command.Reset();
    factory.Reset();
    CoUninitialize();
    std::printf("%s\n", failures ? "shell extension checks FAILED" : "shell extension checks passed");
    return failures ? 1 : 0;
}
