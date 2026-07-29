from pathlib import Path
import xml.etree.ElementTree as ET


def test_msix_manifest_template_has_desktop_entrypoint_and_logo():
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "packaging" / "Package.appxmanifest.in"
    manifest = ET.parse(manifest_path).getroot()

    ns = {
        "foundation": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
        "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
        "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
    }
    application = manifest.find("foundation:Applications/foundation:Application", ns)
    visual = application.find("uap:VisualElements", ns)
    capability = manifest.find("foundation:Capabilities/rescap:Capability", ns)

    assert application.attrib["Executable"] == "CloudHime.exe"
    assert application.attrib["EntryPoint"] == "Windows.FullTrustApplication"
    assert visual.attrib["Square150x150Logo"] == "__LOGO_PATH__"
    assert visual.attrib["Square44x44Logo"] == "__LOGO_PATH__"
    assert visual.attrib["BackgroundColor"] == "#F4F7FB"
    assert capability is not None
    assert capability.attrib["Name"] == "runFullTrust"


def test_msix_builder_requires_windows_sdk_and_expands_manifest():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "build_msix.ps1").read_text(encoding="utf-8")

    assert "makeappx.exe" in script
    assert '[ValidateSet("x64")]' in script
    assert "_internal\\assets\\cloudhime_logo.png" in script
    assert "$packagingSucceeded" in script
    assert "Package.appxmanifest.in" in script
    assert "Windows.FullTrustApplication" not in script
    assert "makeappx pack /d" in script
    assert "THIRD_PARTY_NOTICES.md" in (root / "build_exe.bat").read_text(encoding="utf-8")
    assert (root / "assets" / "cloudhime_logo.png").is_file()

    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "AppxManifest.xml" in ci
    assert "runFullTrust" in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\LocalMachine\\TrustedPeople" in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\CurrentUser\\TrustedPeople" not in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\CurrentUser\\Root" not in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\LocalMachine\\Root" not in ci
    assert '$stores = @("Cert:\\CurrentUser\\My", "Cert:\\LocalMachine\\TrustedPeople")' in ci
    assert "Get-ChildItem -Path $store -ErrorAction Stop" in ci
    assert 'foreach ($store in @("My", "TrustedPeople", "Root"))' not in ci
    assert "CLOUDHIME_CI_CERT_THUMBPRINT" in ci
    assert ci.count("$_.Thumbprint -eq $thumbprint") >= 2
    assert 'Where-Object { $_.Subject -eq "CN=CloudHime CI" }' not in ci
    assert "Remove-Item -Force -ErrorAction Stop" in ci
    assert "Failed to remove CI signing certificate" in ci
    assert "cancel-in-progress: true" in ci
    assert "name: CI" in ci
    assert "fail-fast: false" in ci
    assert "Run Tests (" + "$" + "{{ matrix.name }})" in ci
    assert "Build MSIX package" in ci
    assert "Inspect and sign MSIX package" in ci
    assert "Install and uninstall MSIX package" in ci
    assert ci.count("timeout-minutes: 30") == 2
    assert ci.count("timeout-minutes: 10") >= 3

    install_smoke = (root / "packaging" / "test_msix_install.ps1").read_text(encoding="utf-8")
    assert "Add-AppxPackage" in install_smoke
    assert "Start-Process" in install_smoke
    assert "Remove-AppxPackage" in install_smoke
    assert "Refusing to modify an existing package" in install_smoke
