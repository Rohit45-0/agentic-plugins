import { useState, useEffect } from "react";
import { Settings, User, Bell, Shield, Palette, ChevronRight, Loader2 } from "lucide-react";
import { getCurrentUser } from "../services/auth";
import { apiRequest } from "../services/api";

const sections = [
  {
    icon: User,
    label: "Profile",
    description: "Manage your account and campaign defaults",
    fields: [
      { id: "full_name", label: "Full Name", type: "text", placeholder: "Your name" },
      { id: "email", label: "Email", type: "email", placeholder: "you@company.com", readOnly: true },
    ],
  },
  {
    icon: Bell,
    label: "Notifications",
    description: "Configure alert preferences",
    fields: [],
    toggles: [
      { id: "notify_campaigns", label: "Campaign updates", description: "Get notified when campaigns complete" },
      { id: "notify_weekly", label: "Weekly digest", description: "Summary of your performance" },
    ],
  },
  {
    icon: Shield,
    label: "Security",
    description: "Password and authentication",
    fields: [
      { id: "password", label: "New Password", type: "password", placeholder: "••••••••" },
    ],
  },
];

function Toggle({ label, description }) {
  const [on, setOn] = useState(false);
  return (
    <div className="flex items-center justify-between py-3 border-b border-neutral-100 last:border-0">
      <div>
        <p className="text-sm font-medium text-neutral-900">{label}</p>
        <p className="text-xs text-neutral-500 mt-0.5">{description}</p>
      </div>
      <button
        onClick={() => setOn(!on)}
        className={`relative w-10 h-5 rounded-full transition-colors duration-200 ${on ? "bg-neutral-900" : "bg-neutral-200"}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow-xs transition-transform duration-200 ${on ? "translate-x-5" : ""}`}
        />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState("Profile");
  const [formData, setFormData] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState({ text: "", type: "" });

  useEffect(() => {
    getCurrentUser().then(user => {
      if (user) setFormData(user);
    }).catch(console.error);
  }, []);

  const handleChange = (id, value) => {
    setFormData(prev => ({ ...prev, [id]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMsg({ text: "", type: "" });
    try {
      // Send updates to the backend
      const { email, id, ...updates } = formData;
      await apiRequest("/auth/me", {
        method: "PUT",
        body: JSON.stringify(updates),
      });
      setMsg({ text: "Settings saved successfully", type: "success" });
    } catch (err) {
      setMsg({ text: err.message || "Failed to save settings", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const section = sections.find((s) => s.label === activeSection);

  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-neutral-900 tracking-tight">Settings</h1>
        <p className="text-sm text-neutral-500 mt-0.5">Manage your account and preferences</p>
      </div>

      <div className="flex gap-6 max-w-4xl">
        {/* Sidebar nav */}
        <div className="w-48 flex-shrink-0">
          <nav className="space-y-0.5">
            {sections.map(({ label, icon: Icon }) => (
              <button
                key={label}
                onClick={() => {
                  setActiveSection(label);
                  setMsg({ text: "", type: "" });
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-100 ${activeSection === label
                  ? "bg-neutral-900 text-white"
                  : "text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900"
                  }`}
              >
                <Icon size={15} strokeWidth={1.75} />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 cn-card">
          <div className="flex items-center gap-2 mb-6 border-b border-neutral-100 pb-4">
            {section && <section.icon size={18} className="text-neutral-400" strokeWidth={1.75} />}
            <div>
              <h2 className="text-sm font-semibold text-neutral-900">{section?.label}</h2>
              <p className="text-xs text-neutral-500">{section?.description}</p>
            </div>
          </div>

          {msg.text && (
            <div className={`mb-6 px-3 py-2 rounded-lg text-sm ${msg.type === "success" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
              {msg.text}
            </div>
          )}

          {section?.fields?.length > 0 && (
            <div className="space-y-4 mb-6">
              <div className="grid grid-cols-2 gap-4">
                {section.fields.map((f) => (
                  <div key={f.id} className={f.type === "password" ? "col-span-2" : "col-span-1"}>
                    <label className="block text-xs font-medium text-neutral-700 mb-1.5">{f.label}</label>
                    <input
                      type={f.type}
                      placeholder={f.placeholder}
                      className={`cn-input w-full ${f.readOnly ? "bg-neutral-50 cursor-not-allowed text-neutral-500" : ""}`}
                      value={formData[f.id] || ""}
                      onChange={(e) => handleChange(f.id, e.target.value)}
                      readOnly={f.readOnly}
                    />
                  </div>
                ))}
              </div>
              <button onClick={handleSave} disabled={saving} className="btn-primary mt-4">
                {saving ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
                Save changes
              </button>
            </div>
          )}

          {section?.toggles?.length > 0 && (
            <div>
              {section.toggles.map((t) => (
                <Toggle key={t.id} {...t} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
