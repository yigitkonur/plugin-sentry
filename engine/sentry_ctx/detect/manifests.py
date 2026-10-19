"""Dependency + metadata extraction per manifest format. Format-specific, not language logic:
the decision of what a dependency *means* lives in data/detect/*.json."""
from __future__ import annotations

import fnmatch
import json
import os
import re

from . import toml_mini


def _norm_py(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _py_req_line(line: str):
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "git+", "http", ".")):
        return None
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([<>=!~].*)?$", line.split(";", 1)[0].strip())
    return (_norm_py(m.group(1)), (m.group(3) or "").strip()) if m else None


def package_json(path, text):
    try:
        d = json.loads(text)
    except ValueError:
        return {"deps": {}, "meta": {"parse_error": True}}
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        for k, v in (d.get(key) or {}).items():
            deps.setdefault(k, str(v))
    ws = d.get("workspaces")
    if isinstance(ws, dict):
        ws = ws.get("packages")
    meta = {
        "name": d.get("name"), "private": d.get("private"), "version": d.get("version"),
        "has_main": bool(d.get("main") or d.get("exports") or d.get("module")),
        "has_bin": bool(d.get("bin")), "scripts": sorted((d.get("scripts") or {}).keys()),
        "script_text": {k: v for k, v in (d.get("scripts") or {}).items() if isinstance(v, str)},
        "workspaces": ws if isinstance(ws, list) else None, "engines": d.get("engines"),
        "homepage": d.get("homepage"), "type": d.get("type"), "publish": bool(d.get("publishConfig")),
        "package_manager": d.get("packageManager"),
        "peer": sorted((d.get("peerDependencies") or {}).keys()),
    }
    return {"deps": deps, "meta": meta}


def requirements(path, text):
    deps = {}
    for line in text.splitlines():
        r = _py_req_line(line)
        if r:
            deps.setdefault(r[0], r[1])
    return {"deps": deps, "meta": {}}


def pyproject(path, text):
    d = toml_mini.loads(text)
    deps = {}
    proj = d.get("project") or {}
    for item in proj.get("dependencies") or []:
        r = _py_req_line(str(item))
        if r:
            deps.setdefault(*r)
    for group in (proj.get("optional-dependencies") or {}).values():
        for item in group or []:
            r = _py_req_line(str(item))
            if r:
                deps.setdefault(*r)
    for group in (d.get("dependency-groups") or {}).values():
        for item in group or []:
            if isinstance(item, str):
                r = _py_req_line(item)
                if r:
                    deps.setdefault(*r)
    poetry = (d.get("tool") or {}).get("poetry") or {}
    for sec in ("dependencies", "dev-dependencies"):
        for k, v in (poetry.get(sec) or {}).items():
            if k.lower() != "python":
                deps.setdefault(_norm_py(k), v if isinstance(v, str) else str((v or {}).get("version", "")))
    for grp in (poetry.get("group") or {}).values():
        for k, v in (grp.get("dependencies") or {}).items():
            deps.setdefault(_norm_py(k), v if isinstance(v, str) else str((v or {}).get("version", "")))
    uv = (d.get("tool") or {}).get("uv") or {}
    meta = {
        "name": proj.get("name") or poetry.get("name"), "requires_python": proj.get("requires-python"),
        "has_build_system": "build-system" in d, "has_scripts": bool(proj.get("scripts") or poetry.get("scripts")),
        "workspace_members": (uv.get("workspace") or {}).get("members"),
    }
    return {"deps": deps, "meta": meta}


def pipfile(path, text):
    d = toml_mini.loads(text)
    deps = {}
    for sec in ("packages", "dev-packages"):
        for k, v in (d.get(sec) or {}).items():
            deps.setdefault(_norm_py(k), v if isinstance(v, str) else str((v or {}).get("version", "")))
    return {"deps": deps, "meta": {}}


def setup_py(path, text):
    deps = {}
    for m in re.finditer(r"install_requires\s*=\s*\[(.*?)\]", text, re.S):
        for s in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
            r = _py_req_line(s)
            if r:
                deps.setdefault(*r)
    if path.endswith("setup.cfg"):
        m = re.search(r"install_requires\s*=\s*\n((?:[ \t]+.+\n?)+)", text)
        if m:
            for line in m.group(1).splitlines():
                r = _py_req_line(line)
                if r:
                    deps.setdefault(*r)
    return {"deps": deps, "meta": {"has_setup": True}}


def go_mod(path, text):
    deps = {}
    meta = {}
    m = re.search(r"(?m)^module\s+(\S+)", text)
    meta["module"] = m.group(1) if m else None
    m = re.search(r"(?m)^go\s+(\S+)", text)
    meta["go"] = m.group(1) if m else None
    for block in re.findall(r"(?ms)^require\s*\((.*?)^\)", text):
        for line in block.splitlines():
            line = line.split("//", 1)[0].strip()
            parts = line.split()
            if len(parts) >= 2:
                deps[parts[0]] = parts[1]
    for line in re.findall(r"(?m)^require[ \t]+([^\s(]\S*[ \t]+\S+)", text):
        p = line.split()
        deps[p[0]] = p[1]
    return {"deps": deps, "meta": meta}


def gemfile(path, text):
    deps = {}
    for m in re.finditer(r"(?m)^\s*gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", text):
        deps.setdefault(m.group(1), m.group(2) or "")
    return {"deps": deps, "meta": {}}


def composer_json(path, text):
    try:
        d = json.loads(text)
    except ValueError:
        return {"deps": {}, "meta": {}}
    deps = {}
    for key in ("require", "require-dev"):
        for k, v in (d.get(key) or {}).items():
            deps.setdefault(k, str(v))
    return {"deps": deps, "meta": {"name": d.get("name"), "type": d.get("type")}}


def csproj(path, text):
    deps = {}
    for m in re.finditer(r"<PackageReference\s+[^>]*?Include=\"([^\"]+)\"(?:[^>]*?Version=\"([^\"]*)\")?", text):
        deps.setdefault(m.group(1), m.group(2) or "")
    for m in re.finditer(r"<PackageVersion\s+[^>]*?Include=\"([^\"]+)\"(?:[^>]*?Version=\"([^\"]*)\")?", text):
        deps.setdefault(m.group(1), m.group(2) or "")
    sdk = re.search(r"<Project\s+Sdk=\"([^\"]+)\"", text)
    if sdk and sdk.group(1) == "Microsoft.NET.Sdk.Web":
        deps.setdefault("Microsoft.AspNetCore.App", "")
    if re.search(r"<UseWPF>\s*true", text, re.I):
        deps.setdefault("__wpf__", "")
    if re.search(r"<UseWindowsForms>\s*true", text, re.I):
        deps.setdefault("__winforms__", "")
    meta = {
        "sdk": sdk.group(1) if sdk else None,
        "output_type": (re.search(r"<OutputType>\s*([^<]+)<", text) or [None, None])[1],
        "target_framework": (re.search(r"<TargetFrameworks?>\s*([^<]+)<", text) or [None, None])[1],
    }
    return {"deps": deps, "meta": meta}


def cargo_toml(path, text):
    d = toml_mini.loads(text)
    deps = {}
    for sec in ("dependencies", "dev-dependencies", "build-dependencies"):
        for k, v in (d.get(sec) or {}).items():
            deps.setdefault(k, v if isinstance(v, str) else str((v or {}).get("version", "")) if isinstance(v, dict) else "")
    for tgt in (d.get("target") or {}).values():
        for k in (tgt.get("dependencies") or {}):
            deps.setdefault(k, "")
    ws = d.get("workspace") or {}
    pkg = d.get("package") or {}
    for k in (ws.get("dependencies") or {}):
        deps.setdefault(k, "")
    meta = {"name": pkg.get("name"), "workspace_members": ws.get("members"), "has_bin": bool(d.get("bin")), "has_lib": "lib" in d}
    return {"deps": deps, "meta": meta}


def pom_xml(path, text):
    deps = {}
    for blk in re.findall(r"(?s)<dependency>(.*?)</dependency>", text):
        g = re.search(r"<groupId>([^<]+)<", blk)
        a = re.search(r"<artifactId>([^<]+)<", blk)
        v = re.search(r"<version>([^<]+)<", blk)
        if g and a:
            deps.setdefault("%s:%s" % (g.group(1).strip(), a.group(1).strip()), v.group(1).strip() if v else "")
    for blk in re.findall(r"(?s)<plugin>(.*?)</plugin>", text):
        g = re.search(r"<groupId>([^<]+)<", blk)
        a = re.search(r"<artifactId>([^<]+)<", blk)
        v = re.search(r"<version>([^<]+)<", blk)
        if a:
            deps.setdefault("%s:%s" % ((g.group(1).strip() if g else "org.apache.maven.plugins"), a.group(1).strip()), v.group(1).strip() if v else "")
    parent = re.search(r"(?s)<parent>.*?<artifactId>([^<]+)<.*?</parent>", text)
    if parent:
        deps.setdefault("__parent__:" + parent.group(1).strip(), "")
    modules = re.findall(r"<module>([^<]+)</module>", text)
    return {"deps": deps, "meta": {"modules": modules or None, "packaging": (re.search(r"<packaging>([^<]+)<", text) or [None, None])[1]}}


def gradle(path, text):
    deps = {}
    for m in re.finditer(r"""['"]([A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+)(?::([A-Za-z0-9_.\-$\{\}]+))?['"]""", text):
        deps.setdefault("%s:%s" % (m.group(1), m.group(2)), m.group(3) or "")
    for m in re.finditer(r"""id\s*\(?\s*['"]([A-Za-z0-9_.\-]+)['"]\s*\)?(?:\s*version\s*['"]([^'"]+)['"])?""", text):
        deps.setdefault(m.group(1), m.group(2) or "")
    for m in re.finditer(r"""apply\s+plugin:\s*['"]([A-Za-z0-9_.\-]+)['"]""", text):
        deps.setdefault(m.group(1), "")
    for m in re.finditer(r"""\bio\.sentry\.[a-z.]+""", text):
        deps.setdefault(m.group(0), "")
    for m in re.finditer(r"""libs\.([A-Za-z0-9_.]+)""", text):
        deps.setdefault("libs." + m.group(1), "")
    return {"deps": deps, "meta": {"android": "com.android." in text}}


def sbt(path, text):
    deps = {}
    for m in re.finditer(r"""['"]([A-Za-z0-9_.\-]+)['"]\s*%%?\s*['"]([A-Za-z0-9_.\-]+)['"]\s*%\s*['"]([^'"]+)['"]""", text):
        deps.setdefault("%s:%s" % (m.group(1), m.group(2)), m.group(3))
    return {"deps": deps, "meta": {}}


def mix_exs(path, text):
    deps = {}
    for m in re.finditer(r"\{\s*:([a-z_0-9]+)\s*,\s*(?:\"([^\"]*)\")?", text):
        deps.setdefault(m.group(1), m.group(2) or "")
    return {"deps": deps, "meta": {"app": (re.search(r"app:\s*:([a-z_0-9]+)", text) or [None, None])[1]}}


def pubspec(path, text):
    deps = {}
    sec = None
    for line in text.splitlines():
        if re.match(r"^(dependencies|dev_dependencies|dependency_overrides):\s*$", line):
            sec = line.split(":")[0]
            continue
        if re.match(r"^\S", line):
            sec = None
        if sec:
            m = re.match(r"^\s{2}([A-Za-z0-9_]+):\s*(.*)$", line)
            if m:
                deps.setdefault(m.group(1), m.group(2).strip())
    meta = {"name": (re.search(r"(?m)^name:\s*(\S+)", text) or [None, None])[1], "flutter_sdk": bool(re.search(r"(?m)^\s+sdk:\s*flutter", text))}
    if meta["flutter_sdk"]:
        deps.setdefault("flutter", "sdk")
    return {"deps": deps, "meta": meta}


def package_swift(path, text):
    deps = {}
    for m in re.finditer(r"\.package\s*\(\s*(?:name:\s*\"[^\"]*\"\s*,\s*)?url:\s*\"([^\"]+)\"\s*,\s*([^)]*)\)", text):
        name = os.path.basename(m.group(1)).replace(".git", "")
        v = re.search(r"\"([0-9][^\"]*)\"", m.group(2))
        deps.setdefault(name, "%s %s" % (m.group(2).split(":")[0].strip(), v.group(1) if v else ""))
    for m in re.finditer(r"\.product\s*\(\s*name:\s*\"([^\"]+)\"", text):
        deps.setdefault(m.group(1), "")
    platforms = re.findall(r"\.(macOS|iOS|tvOS|watchOS|visionOS)\s*\(", text)
    meta = {"platforms": sorted(set(p.lower() for p in platforms)),
            "has_executable": bool(re.search(r"\.executableTarget|\.executable\(", text)),
            "has_library": bool(re.search(r"\.library\(", text)), "tools_version": (re.search(r"swift-tools-version:\s*([0-9.]+)", text) or [None, None])[1]}
    return {"deps": deps, "meta": meta}


def pbxproj(path, text):
    deps = {}
    for m in re.finditer(r"XCRemoteSwiftPackageReference\s+\"([^\"]+)\"\s*\*/\s*=\s*\{(.*?)\};", text, re.S):
        req = re.search(r"kind\s*=\s*(\w+);(?:.*?minimumVersion\s*=\s*([\d.]+);)?", m.group(2), re.S)
        deps.setdefault(m.group(1), ("%s %s" % (req.group(1), req.group(2) or "")).strip() if req else "")
    sdkroots = set(re.findall(r"SDKROOT\s*=\s*(\w+);", text))
    supported = set(re.findall(r"SUPPORTED_PLATFORMS\s*=\s*\"?([^;\"]+)\"?;", text))
    ptypes = set(re.findall(r"productType\s*=\s*\"([^\"]+)\"", text))
    is_app = any("product-type.application" in p for p in ptypes)
    meta = {
        "sdkroots": sorted(sdkroots), "supported_platforms": sorted(supported), "product_types": sorted(ptypes), "is_app": is_app,
        "bundle_ids": sorted(set(re.findall(r"PRODUCT_BUNDLE_IDENTIFIER\s*=\s*\"?([^;\"]+)\"?;", text)))[:5],
        "macos_deployment": sorted(set(re.findall(r"MACOSX_DEPLOYMENT_TARGET\s*=\s*([\d.]+);", text))),
        "ios_deployment": sorted(set(re.findall(r"IPHONEOS_DEPLOYMENT_TARGET\s*=\s*([\d.]+);", text))),
        "user_script_sandboxing": sorted(set(re.findall(r"ENABLE_USER_SCRIPT_SANDBOXING\s*=\s*(\w+);", text))),
        "run_script_sentry": bool(re.search(r"shellScript\s*=\s*\"[^\"]*(sentry-cli|sentry\s)[^\"]*\"", text)),
        "swiftui": False,
    }
    return {"deps": deps, "meta": meta}


def podfile(path, text):
    deps = {}
    for m in re.finditer(r"(?m)^\s*pod\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", text):
        deps.setdefault(m.group(1), m.group(2) or "")
    return {"deps": deps, "meta": {"cocoapods": True}}


def cartfile(path, text):
    deps = {}
    for m in re.finditer(r"(?m)^\s*(?:github|git|binary)\s+\"([^\"]+)\"", text):
        deps.setdefault(os.path.basename(m.group(1)), "")
    return {"deps": deps, "meta": {"carthage": True}}


def unity_manifest(path, text):
    try:
        d = json.loads(text)
    except ValueError:
        return {"deps": {}, "meta": {}}
    return {"deps": {k: str(v) for k, v in (d.get("dependencies") or {}).items()}, "meta": {}}


def uproject(path, text):
    try:
        d = json.loads(text)
    except ValueError:
        return {"deps": {}, "meta": {}}
    return {"deps": {p.get("Name"): "" for p in d.get("Plugins", []) if isinstance(p, dict) and p.get("Name")}, "meta": {}}


def cmake(path, text):
    deps = {}
    for m in re.finditer(r"(?i)find_package\s*\(\s*([A-Za-z0-9_\-]+)", text):
        deps.setdefault(m.group(1), "")
    for m in re.finditer(r"(?i)add_subdirectory\s*\(\s*([^\s)]*sentry[^\s)]*)", text):
        deps.setdefault("sentry-native", m.group(1))
    return {"deps": deps, "meta": {"project": (re.search(r"(?i)project\s*\(\s*([A-Za-z0-9_\-]+)", text) or [None, None])[1]}}


def vcpkg(path, text):
    try:
        d = json.loads(text)
    except ValueError:
        return {"deps": {}, "meta": {}}
    deps = {}
    for x in d.get("dependencies", []):
        deps[x if isinstance(x, str) else x.get("name", "")] = ""
    return {"deps": deps, "meta": {}}


def conan(path, text):
    deps = {}
    for m in re.finditer(r"(?m)^\s*([a-z0-9_\-]+)/([0-9][^\s@]*)", text):
        deps.setdefault(m.group(1), m.group(2))
    return {"deps": deps, "meta": {}}


PARSERS = [
    ("package.json", package_json), ("requirements*.txt", requirements), ("requirements.in", requirements),
    ("pyproject.toml", pyproject), ("Pipfile", pipfile), ("setup.py", setup_py), ("setup.cfg", setup_py),
    ("go.mod", go_mod), ("Gemfile", gemfile), ("composer.json", composer_json),
    ("*.csproj", csproj), ("*.fsproj", csproj), ("*.vbproj", csproj), ("Directory.Packages.props", csproj),
    ("Cargo.toml", cargo_toml), ("pom.xml", pom_xml), ("build.gradle", gradle), ("build.gradle.kts", gradle),
    ("build.sbt", sbt), ("mix.exs", mix_exs), ("pubspec.yaml", pubspec), ("Package.swift", package_swift),
    ("project.pbxproj", pbxproj), ("Podfile", podfile), ("Cartfile", cartfile),
    ("manifest.json@Packages", unity_manifest), ("*.uproject", uproject), ("CMakeLists.txt", cmake),
    ("vcpkg.json", vcpkg), ("conanfile.txt", conan),
]


def parse(rel_path: str, text: str):
    base = os.path.basename(rel_path)
    parent = os.path.basename(os.path.dirname(rel_path))
    for pat, fn in PARSERS:
        if "@" in pat:
            name, par = pat.split("@")
            if base == name and parent == par:
                return fn(rel_path, text)
        elif fnmatch.fnmatch(base, pat):
            return fn(rel_path, text)
    return {"deps": {}, "meta": {}}
