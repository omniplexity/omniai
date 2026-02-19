import { RegistryPackage, ToolPin } from "../../types";

interface RegistryPanelProps {
  registryPackages: RegistryPackage[];
  selectedPkg: string;
  selectedPkgVersion: string;
  projectPins: ToolPin[];
  pinToolId: string;
  pinToolVersion: string;
  mirrorToPackageId: string;
  statusToSet: string;
  isAdmin: boolean;
  selectedProjectId: string;
  selectedRunId: string;
  onInstallPackage: () => void;
  onSelectPackage: (pkg: string) => void;
  onPackageVersionChange: (version: string) => void;
  onSetPin: () => void;
  onUninstallPinned: (toolId: string) => void;
  onPinToolIdChange: (id: string) => void;
  onPinToolVersionChange: (version: string) => void;
  onVerifyPackage: () => void;
  onSetPackageStatus: () => void;
  onMirrorPackage: () => void;
  onMirrorToChange: (id: string) => void;
  onStatusToSetChange: (status: string) => void;
}

export function RegistryPanel(props: RegistryPanelProps) {
  const {
    registryPackages, selectedPkg, selectedPkgVersion, projectPins, pinToolId, pinToolVersion, mirrorToPackageId, statusToSet,
    isAdmin, selectedProjectId, selectedRunId, onInstallPackage, onSelectPackage, onPackageVersionChange, onSetPin,
    onUninstallPinned, onPinToolIdChange, onPinToolVersionChange, onVerifyPackage, onSetPackageStatus,
    onMirrorPackage, onMirrorToChange, onStatusToSetChange,
  } = props;

  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Marketplace</span></div>
      <div className="section-content">
        <select className="input mb-sm" value={selectedPkg} onChange={(e) => onSelectPackage(e.target.value)}>
          <option value="">Select package...</option>
          {registryPackages.map((p) => <option key={`${p.package_id}-${p.version}`} value={p.package_id}>{p.package_id}@{p.version} [{p.tier}/{p.status}]</option>)}
        </select>
        <input type="text" className="input mb-sm" placeholder="Version" value={selectedPkgVersion} onChange={(e) => onPackageVersionChange(e.target.value)} />
        <button className="btn btn-primary btn-sm mb-sm" onClick={onInstallPackage} disabled={!selectedRunId || !selectedProjectId || !selectedPkg}>Install</button>

        <div className="mt-md mb-sm">
          <div className="text-sm font-medium mb-sm">Project Pins</div>
          <div className="list">
            {projectPins.map((p) => (
              <div key={p.tool_id} className="list-item">
                <div className="list-item-content"><div className="list-item-title">{p.tool_id}@{p.tool_version}</div></div>
                <button className="btn btn-ghost btn-sm" onClick={() => onUninstallPinned(p.tool_id)}>×</button>
              </div>
            ))}
          </div>
          <div className="flex gap-xs mt-sm">
            <input type="text" className="input" placeholder="tool_id" value={pinToolId} onChange={(e) => onPinToolIdChange(e.target.value)} />
            <input type="text" className="input" placeholder="version" value={pinToolVersion} onChange={(e) => onPinToolVersionChange(e.target.value)} style={{ width: "80px" }} />
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onSetPin} disabled={!selectedProjectId || !selectedRunId}>Set Pin</button>
        </div>

        {isAdmin && (
          <div className="mt-md">
            <div className="text-sm font-medium mb-sm">Admin</div>
            <div className="flex gap-xs mb-sm">
              <button className="btn btn-success btn-sm" onClick={onVerifyPackage} disabled={!selectedRunId || !selectedPkg}>Verify</button>
              <input type="text" className="input" placeholder="status" value={statusToSet} onChange={(e) => onStatusToSetChange(e.target.value)} style={{ width: "80px" }} />
              <button className="btn btn-secondary btn-sm" onClick={onSetPackageStatus} disabled={!selectedRunId || !selectedPkg}>Set</button>
            </div>
            <div className="flex gap-xs">
              <input type="text" className="input" placeholder="mirror to..." value={mirrorToPackageId} onChange={(e) => onMirrorToChange(e.target.value)} />
              <button className="btn btn-ghost btn-sm" onClick={onMirrorPackage} disabled={!selectedRunId || !selectedPkg || !mirrorToPackageId}>Mirror</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
