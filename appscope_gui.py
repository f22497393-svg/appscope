import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from functools import partial
import subprocess 
import os 
import re 

# --- Global Style Variables ---
COLOR_PRIMARY = "#059669" # Emerald Green
COLOR_SECONDARY = "#1f2937"
COLOR_DANGER = "#dc2626"
COLOR_SAFE = "#10b981"
COLOR_WARNING = "#f59e0b"
COLOR_BG = "#f9fafb"

RISK_COLORS = {
    "Low": COLOR_SAFE,
    "Medium": COLOR_WARNING,
    "High": COLOR_DANGER
}

TYPE_COLORS = {
    "Flatpak": "#3b82f6", # Blue
    "Snap": "#8b5cf6",    # Purple
    "Native": "#6b7280"   # Gray
}

# --- Fallback Data (Only used if ALL system scans fail) ---
FALLBACK_APPDATA = [
    {"id": 1, "name": "Firefox (Fallback)", "type": "Native", "package_id": "firefox", "risk": "Low", "permissions": [{"id": 101, "name": "Network Access", "status": "Enabled"}]},
    {"id": 2, "name": "VS Code (Fallback)", "type": "Snap", "package_id": "code", "risk": "Medium", "permissions": [{"id": 202, "name": "Home Directory Access", "status": "Enabled"}]},
]

# --- SYSTEM INTEGRATION CLASS (The Real Engine) ---

class SystemIntegrator:
    """
    Manages all interaction with the host operating system using subprocess.
    This class executes live Linux commands.
    """
    
    def __init__(self, initial_data):
        self.app_data = initial_data
        self.next_app_id = len(initial_data) + 1

    def _run_system_command(self, command):
        """
        Helper to run a system command and return output or raise error.
        THIS IS NOW LIVE.
        """
        try:
            # Executes the command (e.g., 'flatpak list').
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            # Errors will be printed to your terminal.
            print(f"Command failed: {' '.join(command)}\nError: {e.stderr}")
            raise RuntimeError(f"Command Failed: {command[0]}") from e
        except FileNotFoundError:
            print(f"Command not found: {command[0]}. Is the package manager installed?")
            raise RuntimeError(f"Dependency Missing: {command[0]}") from None
        except Exception as e:
            print(f"An unexpected error occurred in system call: {e}")
            raise RuntimeError("System Command Failed") from e

    def _get_app_permissions(self, package_id, app_type):
        """
        Simulates parsing the actual permission status for a given app.
        NOTE: This function is the primary target for implementing live status
        reading based on system tools like 'flatpak info' or 'snap connections'.
        """
        permissions = []
        
        # --- BLUEPRINT FOR REAL PERMISSION SCANNING ---
        # TO MAKE THIS REAL: You must execute 'flatpak info' or 'snap connections'
        # and parse the output here to determine the actual 'status'.

        if app_type == 'Flatpak':
            # Example: A Flatpak app will typically have some permissions
            permissions.append({"id": 301, "name": "Network Access", "status": "Denied" if "calculator" in package_id.lower() else "Enabled"})
            permissions.append({"id": 304, "name": "User Documents Folder", "status": "Read/Write"})
        elif app_type == 'Snap':
            # Example: A Snap app might have home access
            permissions.append({"id": 202, "name": "Home Directory Access", "status": "Enabled"})
            permissions.append({"id": 201, "name": "Network Access", "status": "Enabled"})
        elif app_type == 'Native': 
            # Example: Native apps generally have broad access, often marked as "Unrestricted"
            permissions.append({"id": 101, "name": "System Access", "status": "Unrestricted"})
            permissions.append({"id": 102, "name": "Network Access", "status": "Enabled"})
        
        return permissions

    def _scan_flatpak_apps(self):
        """Scans and parses Flatpak applications using 'flatpak list'."""
        flatpak_apps = []
        try:
            output = self._run_system_command(['flatpak', 'list', '--app', '--columns=application,name'])
        except Exception:
            return flatpak_apps # Return empty if flatpak command fails

        if output:
            lines = output.strip().split('\n')
            for line in lines[1:]: # Skip header
                parts = line.split('\t')
                if len(parts) >= 2:
                    package_id = parts[0].strip()
                    app_name = parts[1].strip()
                    
                    flatpak_apps.append({
                        "id": self.next_app_id,
                        "name": app_name or package_id.split('.')[-1],
                        "type": "Flatpak",
                        "package_id": package_id,
                        # Permissions are simulated status until full parsing is implemented
                        "permissions": self._get_app_permissions(package_id, "Flatpak")
                    })
                    self.next_app_id += 1
        return flatpak_apps

    def _scan_snap_apps(self):
        """Scans and parses Snap applications using 'snap list'."""
        snap_apps = []
        try:
            output = self._run_system_command(['snap', 'list'])
        except Exception:
            return snap_apps # Return empty if snap command fails
        
        if output:
            lines = output.strip().split('\n')
            if len(lines) > 1:
                for line in lines[1:]: # Skip header
                    parts = re.split(r'\s+', line.strip())
                    if len(parts) >= 2:
                        package_id = parts[0]
                        
                        if package_id in ('core', 'snapd'):
                            continue

                        snap_apps.append({
                            "id": self.next_app_id,
                            "name": package_id.capitalize(),
                            "type": "Snap",
                            "package_id": package_id,
                            # Permissions are simulated status until full parsing is implemented
                            "permissions": self._get_app_permissions(package_id, "Snap")
                        })
                        self.next_app_id += 1
        return snap_apps
        
    def _scan_apt_apps(self):
        """
        Scans and parses native APT applications using 'dpkg --get-selections'.
        Filters for likely GUI applications.
        """
        native_apps = []
        # Use simple 'dpkg -l' which doesn't require sudo to read package names
        try:
            output = self._run_system_command(['dpkg', '-l'])
        except Exception:
            return native_apps # Return empty if dpkg command fails
            
        if output:
            lines = output.strip().split('\n')
            for line in lines:
                if line.startswith('ii'): # 'ii' means installed
                    parts = line.split()
                    package_id = parts[1]
                    
                    # Simple filter to grab common desktop apps and ignore libraries/dev tools
                    is_desktop_app = any(keyword in package_id for keyword in [
                        'firefox', 'chrome', 'discord', 'thunderbird', 'gimp', 'kdenlive', 
                        'libreoffice', 'vlc', 'krita', 'gnome-shell', 'kde-plasma', 'app'
                    ])

                    # Basic check to exclude complex libraries and kernel modules
                    if is_desktop_app and not any(ext in package_id for ext in ['dev', 'lib', 'common', 'data', 'doc', 'tools']):
                        
                        # Generate a cleaner name by capitalizing and splitting
                        clean_name = package_id.replace('-', ' ').title()
                        
                        native_apps.append({
                            "id": self.next_app_id,
                            "name": clean_name,
                            "type": "Native",
                            "package_id": package_id,
                            # Permissions are simulated status until full parsing is implemented
                            "permissions": self._get_app_permissions(package_id, "Native")
                        })
                        self.next_app_id += 1
        return native_apps


    def scan_system(self):
        """Runs all scanners and populates the app list."""
        self.app_data = []
        self.next_app_id = 1
        app_list_from_system = []
        scan_failed = False

        try:
            app_list_from_system.extend(self._scan_flatpak_apps())
            app_list_from_system.extend(self._scan_snap_apps())
            app_list_from_system.extend(self._scan_apt_apps()) # NEW APT SCAN
            
        except RuntimeError:
            scan_failed = True

        if not app_list_from_system:
            print("Loading full fallback data due to empty scan results.")
            self.app_data = FALLBACK_APPDATA
            scan_failed = True
        else:
            self.app_data = app_list_from_system

        # Calculate risk for all loaded apps
        for app in self.app_data:
            app['risk'] = self.calculate_risk(app)
        
        return self.app_data, scan_failed
        
    def calculate_risk(self, app):
        """Dynamically calculates the risk level based on package type and permissions."""
        score = 0
        risk_map = {"Flatpak": 1, "Snap": 2, "Native": 4} # Native is highest risk due to lack of standard sandbox
        score += risk_map.get(app['type'], 2)
        
        for p in app['permissions']:
            if p['status'] in ('Enabled', 'Read/Write', 'Unrestricted'):
                if "Root Access" in p['name'] or "Unrestricted" in p['name']:
                    score += 5 
                elif "Network Access" in p['name'] and app['type'] == 'Native':
                    score += 2 # Native networking is generally a medium risk
                elif "Home Directory" in p['name'] and app['type'] in ('Snap', 'Flatpak'):
                    score += 3 

        if score > 6:
            return "High"
        elif score > 3:
            return "Medium"
        else:
            return "Low"

    def update_permission(self, app_id, permission_id, new_status):
        """
        Executes the command to change a permission using 'pkexec' for elevation.
        """
        app = next((a for a in self.app_data if a['id'] == app_id), None)
        permission = next((p for p in app['permissions'] if p['id'] == permission_id), None)

        if app and permission:
            command = []
            try:
                if app['type'] == 'Flatpak':
                    if "Network Access" in permission['name']:
                        action = '--unshare=network' if new_status == 'Denied' else '--share=network'
                        command = ['flatpak', 'override', app['package_id'], action]
                        
                elif app['type'] == 'Snap':
                    interface = "home" if "Home Directory" in permission['name'] else "network"
                    action = "connect" if new_status == 'Enabled' else 'disconnect'
                    command = ['pkexec', 'snap', action, app['package_id'], interface] 
                
                if command:
                    # LIVE EXECUTION
                    subprocess.run(command, check=True) 

            except subprocess.CalledProcessError as e:
                print(f"Permission Update FAILED: {' '.join(command)} - {e}")
                return False
            
            # --- FEATURE: LIVE STATUS REFRESH ---
            # After a successful change, re-scan the system to verify and update the list.
            self.app_data, _ = self.scan_system()
            # If full parsing were implemented, this would fetch the REAL new status.
            # For now, we update the local object to match the user's intent.
            permission['status'] = new_status
            app['risk'] = self.calculate_risk(app) 
            # -----------------------------------
            return True
        return False

    def uninstall_app(self, app_id):
        """
        Executes the command to uninstall an application using 'pkexec' for elevation.
        """
        app = next((a for a in self.app_data if a['id'] == app_id), None)
        if app:
            command = []
            try:
                if app['type'] == 'Flatpak':
                    command = ['pkexec', 'flatpak', 'uninstall', app['package_id'], '-y'] 
                elif app['type'] == 'Snap':
                    command = ['pkexec', 'snap', 'remove', app['package_id']]
                elif app['type'] == 'Native': 
                    # Use remove command for native packages
                    command = ['pkexec', 'apt', 'remove', app['package_id'], '-y'] 
                
                if command:
                    # LIVE EXECUTION
                    subprocess.run(command, check=True) 

            except subprocess.CalledProcessError as e:
                print(f"Uninstall FAILED: {' '.join(command)} - {e}")
                return False
            
            # If system command succeeds, update state
            self.app_data = [a for a in self.app_data if a['id'] != app_id]
            return True
        return False
        
# --- Main GUI Class ---

class AppScope(tk.Tk):
    """
    Main application window for AppScope: The Linux Security Console.
    """
    def __init__(self):
        super().__init__()
        self.app_manager = SystemIntegrator(FALLBACK_APPDATA)
        
        self.title("AppScope: Linux Security Console")
        self.geometry("950x700")
        
        # Initial Theme Configuration (Customizable)
        self.current_theme = {
            'primary': COLOR_PRIMARY,
            'secondary': COLOR_SECONDARY,
            'bg': COLOR_BG
        }
        
        self.configure(bg=self.current_theme['bg'])
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.apply_styles()
        self.create_widgets()
        
        # Initial Scan (Delay added to ensure status label renders first)
        self.show_status("Running initial system scan...", COLOR_PRIMARY)
        self.after(100, self._perform_scan_and_update)
        
        self.current_app_id = None 

    def apply_styles(self):
        """Sets or refreshes Tkinter styles based on current_theme."""
        
        # TTK Style Initialization
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        
        # Configure Frames and Labels based on theme
        self.style.configure('TFrame', background='white')
        self.style.configure('TLabel', background='white', foreground=self.current_theme['secondary'])
        self.style.configure('TButton', background=self.current_theme['primary'], foreground='white', font=('Inter', 10, 'bold'))
        self.style.configure('AppBg.TFrame', background=self.current_theme['bg'])
        
        # Configure Colored Buttons
        self.style.configure('Danger.TButton', background=COLOR_DANGER, foreground='white')
        self.style.map('Danger.TButton', background=[('active', '#b91c1c')])
        self.style.configure('Safe.TButton', background=COLOR_SAFE, foreground='white')
        self.style.map('Safe.TButton', background=[('active', '#047857')])

    def create_widgets(self):
        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))

        # --- Tab 1: Dashboard (Main View) ---
        dashboard_frame = ttk.Frame(self.notebook, style='AppBg.TFrame', padding="10")
        self.notebook.add(dashboard_frame, text="🛡️ Security Dashboard")
        self.create_dashboard(dashboard_frame)

        # --- Tab 2: Settings (Customization) ---
        settings_frame = ttk.Frame(self.notebook, style='AppBg.TFrame', padding="20")
        self.notebook.add(settings_frame, text="⚙️ Settings & Appearance")
        self.create_settings_panel(settings_frame)

        # 5. Status Message (Bottom)
        self.status_label = tk.Label(self, text="", fg="white", bg=COLOR_SECONDARY, bd=0, relief="flat", font=('Inter', 10), anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew")

    def create_dashboard(self, parent_frame):
        """Creates the main app list and detail panels."""
        parent_frame.grid_rowconfigure(1, weight=1)
        parent_frame.grid_columnconfigure(0, weight=2)
        parent_frame.grid_columnconfigure(1, weight=1)

        # Header
        header_frame = tk.Frame(parent_frame, bg=self.current_theme['bg'], padx=0, pady=0)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Title and Subtitle
        tk.Label(header_frame, text="AppScope: Unified Security", font=('Inter', 20, 'bold'), fg=self.current_theme['primary'], bg=self.current_theme['bg']).pack(anchor="w")
        tk.Label(header_frame, text="Audit, modify, and manage security access across all package types.", fg="#6b7280", bg=self.current_theme['bg']).pack(anchor="w")

        # --- REFRESH BUTTON FRAME ---
        refresh_frame = tk.Frame(header_frame, bg=self.current_theme['bg'])
        refresh_frame.pack(anchor="w", fill='x', pady=(10, 0))

        ttk.Button(refresh_frame, 
                   text="🔄 Refresh App List (Live Scan)", 
                   command=self.refresh_data).pack(side='left')
        # --- END REFRESH FRAME ---

        # 3. Application List Panel (Left)
        list_panel = ttk.Frame(parent_frame, padding=10)
        list_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        list_panel.grid_rowconfigure(1, weight=1)
        
        ttk.Label(list_panel, text="Installed Applications", font=('Inter', 14, 'bold')).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        self.app_list_canvas = tk.Canvas(list_panel, background="white", highlightthickness=0)
        self.app_list_canvas.grid(row=1, column=0, sticky="nsew")
        
        self.app_list_frame = ttk.Frame(self.app_list_canvas, padding=5)
        self.app_list_canvas.create_window((0, 0), window=self.app_list_frame, anchor="nw", width=550) # Set a fixed initial width
        self.app_list_frame.bind("<Configure>", lambda e: self.app_list_canvas.configure(scrollregion=self.app_list_frame.bbox("all")))
        self.app_list_frame.grid_columnconfigure(0, weight=1)

        list_scrollbar = ttk.Scrollbar(list_panel, orient="vertical", command=self.app_list_canvas.yview)
        list_scrollbar.grid(row=1, column=1, sticky="ns")
        self.app_list_canvas.configure(yscrollcommand=list_scrollbar.set)

        # 4. Detail Panel (Right)
        self.detail_panel = ttk.Frame(parent_frame, padding=10)
        self.detail_panel.grid(row=1, column=1, sticky="nsew")
        self.detail_panel.grid_rowconfigure(1, weight=1)
        
        ttk.Label(self.detail_panel, text="App Details & Permissions", font=('Inter', 14, 'bold')).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        self.permission_details_frame = ttk.Frame(self.detail_panel, padding=5)
        self.permission_details_frame.grid(row=1, column=0, sticky="nsew")
        self.show_placeholder()

    def refresh_data(self):
        """Triggers a system scan and updates the GUI."""
        self.show_status("Scanning system for changes...", COLOR_PRIMARY)
        self.after(100, self._perform_scan_and_update)

    def _perform_scan_and_update(self):
        """Performs the scan and updates the GUI, called after a slight delay."""
        try:
            _, scan_failed = self.app_manager.scan_system()
            self.render_app_list()
            self.show_placeholder()
            
            if scan_failed:
                self.show_status("Scan Complete. Some package managers failed to respond or returned empty results.", COLOR_WARNING)
            else:
                self.show_status("Scan Complete. App list updated.", COLOR_SAFE)
        except Exception as e:
            self.show_status(f"Fatal Scan Error: {e}", COLOR_DANGER)


    def create_settings_panel(self, parent_frame):
        """Creates the panel for user customization (Theme, Background, Logos)."""
        
        tk.Label(parent_frame, 
                 text="Appearance Settings", 
                 font=('Inter', 18, 'bold'), 
                 fg=self.current_theme['primary'], 
                 bg=self.current_theme['bg']).pack(anchor="w", pady=(0, 15))

        # --- 1. Theme Color Chooser ---
        theme_frame = ttk.Frame(parent_frame, padding=15)
        theme_frame.pack(fill='x', pady=5, padx=10)
        ttk.Label(theme_frame, text="Primary Theme Color:", font=('Inter', 12, 'bold')).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        self.color_display = tk.Label(theme_frame, text="  ", bg=self.current_theme['primary'], width=4)
        self.color_display.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        ttk.Button(theme_frame, 
                   text="Select Color", 
                   command=self.choose_primary_color).grid(row=0, column=2, padx=15, sticky='w')

        # --- 2. Background Color Chooser ---
        bg_frame = ttk.Frame(parent_frame, padding=15)
        bg_frame.pack(fill='x', pady=5, padx=10)
        ttk.Label(bg_frame, text="App Background Color:", font=('Inter', 12, 'bold')).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        self.bg_display = tk.Label(bg_frame, text="  ", bg=self.current_theme['bg'], width=4)
        self.bg_display.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        ttk.Button(bg_frame, 
                   text="Select Background", 
                   command=self.choose_background_color).grid(row=0, column=2, padx=15, sticky='w')
                   
        # --- 3. Logo/Icon Customization (Blueprint) ---
        logo_frame = ttk.Frame(parent_frame, padding=15)
        logo_frame.pack(fill='x', pady=(20, 5), padx=10)
        tk.Label(logo_frame, 
                 text="Logo & Icon Customization (Blueprint)", 
                 font=('Inter', 12, 'bold'), 
                 fg=COLOR_SECONDARY).pack(anchor="w")
        
        # Icon Path Input
        ttk.Label(logo_frame, text="New Icon Path (.png or .svg):", foreground="#6b7280").pack(anchor="w", pady=(5, 2))
        self.icon_path_entry = ttk.Entry(logo_frame, width=50)
        self.icon_path_entry.pack(anchor="w", fill='x')
        
        ttk.Button(logo_frame, 
                   text="Apply Icon Change (Requires manual file editing)", 
                   command=self.apply_icon_change).pack(anchor="w", pady=10)
        
        tk.Label(logo_frame, 
                 text="Requires finding and modifying the target application's .desktop file.", 
                 fg="#6b7280", 
                 wraplength=400).pack(anchor="w")

    def apply_icon_change(self):
        """Mocks the icon change and tells user where to find the blueprint."""
        icon_path = self.icon_path_entry.get().strip()
        if not icon_path:
            self.show_status("Please enter a valid path to an icon file.", COLOR_WARNING)
            return

        # Blueprint for the user
        self.show_status(f"Icon change BLUEPRINT: On your host system, you need to write Python code to edit the .desktop file and run 'gtk-update-icon-cache'.", COLOR_WARNING)
    
    def choose_primary_color(self):
        """Opens color chooser for the primary theme color."""
        color_code = colorchooser.askcolor(title="Choose Primary Theme Color")[1]
        if color_code:
            self.current_theme['primary'] = color_code
            self.color_display.config(bg=color_code)
            self.reapply_theme()
            self.show_status(f"Primary theme color set to {color_code}!", COLOR_SAFE)

    def choose_background_color(self):
        """Opens color chooser for the main background color."""
        color_code = colorchooser.askcolor(title="Choose Background Color")[1]
        if color_code:
            self.current_theme['bg'] = color_code
            self.bg_display.config(bg=color_code)
            self.reapply_theme()
            self.show_status(f"Background color set to {color_code}!", COLOR_SAFE)

    def reapply_theme(self):
        """Reapplies styles and refreshes the main UI."""
        self.configure(bg=self.current_theme['bg'])
        self.apply_styles()
        self.render_app_list()
        self.notebook.winfo_children()[0].config(style='AppBg.TFrame')
        self.notebook.winfo_children()[1].config(style='AppBg.TFrame')


    def show_placeholder(self):
        """Displays the 'Select an app' placeholder message."""
        for widget in self.permission_details_frame.winfo_children():
            widget.destroy()

        placeholder_label = tk.Label(self.permission_details_frame, 
                                     text="Select an application on the left to view and modify its security settings.",
                                     fg="#9ca3af",
                                     font=('Inter', 10, 'italic'),
                                     wraplength=200,
                                     justify="center",
                                     bg='white')
        placeholder_label.pack(expand=True, fill="both", padx=20, pady=50)

    def render_app_list(self):
        """Generates the list of applications in the left panel."""
        for widget in self.app_list_frame.winfo_children():
            widget.destroy()

        apps = self.app_manager.app_data # Use existing data, scan_system populates this

        for i, app in enumerate(apps):
            app_frame = ttk.Frame(self.app_list_frame, padding=10, relief='solid')
            app_frame.grid(row=i, column=0, sticky="ew", pady=5)
            app_frame.grid_columnconfigure(0, weight=1)
            
            select_button = ttk.Button(app_frame, text=f"  {app['name']}", style='App.TButton', command=partial(self.show_app_details, app))
            select_button.grid(row=0, column=0, sticky="w")
            
            # Badges and Risk
            risk_color = RISK_COLORS[app['risk']]
            
            # Badge
            badge_label = tk.Label(app_frame, text=app['type'], bg=TYPE_COLORS[app['type']], fg='white', font=('Inter', 8, 'bold'), relief='flat', padx=5, pady=2)
            badge_label.grid(row=0, column=1, padx=(5, 10), sticky="e")
            
            # Risk Label
            risk_label = tk.Label(app_frame, text=f"Risk: {app['risk']}", bg='white', fg=risk_color, font=('Inter', 10, 'bold'))
            risk_label.grid(row=0, column=2, sticky="e")

    def show_app_details(self, app):
        """Renders the detailed permissions and action buttons for the selected app."""
        self.current_app_id = app["id"]
        
        for widget in self.permission_details_frame.winfo_children():
            widget.destroy()

        # App Info
        ttk.Label(self.permission_details_frame, text=app['name'], font=('Inter', 16, 'bold')).pack(anchor="w", pady=(0, 5))
        ttk.Label(self.permission_details_frame, text=f"Package Type: {app['type']} | Current Risk: {app['risk']}", foreground="#6b7280").pack(anchor="w", pady=(0, 10))
        
        # --- NEW UTILITY ACTION FRAME ---
        utility_frame = ttk.Frame(self.permission_details_frame, padding=(0, 10))
        utility_frame.pack(fill='x', pady=5)
        
        ttk.Button(utility_frame,
                   text="📂 Open Config Folder",
                   command=partial(self.open_config_folder, app)
                  ).pack(side='left', padx=5)
        # --- END UTILITY ACTION FRAME ---
        
        # Permissions Header
        ttk.Separator(self.permission_details_frame).pack(fill="x", pady=10)
        ttk.Label(self.permission_details_frame, 
                  text="Runtime Permissions:", 
                  font=('Inter', 12, 'bold')).pack(anchor="w", pady=(5, 5))
        
        # Permissions List container
        permissions_frame = ttk.Frame(self.permission_details_frame, padding=5)
        permissions_frame.pack(fill="x")
        permissions_frame.grid_columnconfigure(0, weight=1)

        for i, p in enumerate(app['permissions']):
            self.render_permission_row(permissions_frame, p, i, app['id'])
            
        # --- Uninstall Section ---
        ttk.Separator(self.permission_details_frame).pack(fill="x", pady=15)
        
        uninstall_frame = ttk.Frame(self.permission_details_frame, padding=10)
        uninstall_frame.pack(fill='x')
        
        ttk.Label(uninstall_frame, 
                  text="Dangerous Action: Uninstall Application", 
                  font=('Inter', 12, 'bold'),
                  foreground=COLOR_DANGER).grid(row=0, column=0, sticky='w')
                  
        ttk.Button(uninstall_frame, 
                   text=f"Uninstall {app['name']}",
                   style='Danger.TButton',
                   command=partial(self.confirm_uninstall, app['name'], app['id'])
                   ).grid(row=0, column=1, padx=10)
        
        ttk.Label(uninstall_frame, 
                  text="Warning: Requires elevated privileges (pkexec) on host system.", 
                  foreground=COLOR_WARNING).grid(row=1, column=0, columnspan=2, sticky='w')

    def open_config_folder(self, app):
        """Opens the assumed configuration folder for the selected app."""
        
        config_dir = ""
        app_name_clean = app['package_id'].replace('-', '_')
        
        if app['type'] == 'Flatpak':
             # Common location for Flatpak runtimes/configs
             config_dir = os.path.expanduser(f"~/.var/app/{app['package_id']}")
        elif app['type'] == 'Snap':
             # Snap's current symlink pointing to the live version
             config_dir = os.path.expanduser(f"~/snap/{app['package_id']}/current")
        elif app['type'] == 'Native':
             # Default to XDG Base Directory Specification for Native apps
             config_dir = os.path.expanduser(f"~/.config/{app_name_clean}")
             
        try:
            if config_dir:
                # Use xdg-open to launch the default file manager at the path
                subprocess.run(['xdg-open', config_dir], check=True)
                self.show_status(f"Opening directory: {config_dir}", COLOR_SAFE)
            else:
                self.show_status("Could not determine configuration directory for this app type.", COLOR_WARNING)
        except subprocess.CalledProcessError as e:
            self.show_status(f"Failed to open folder. Is xdg-open installed? Error: {e.returncode}", COLOR_WARNING)
        except Exception:
             self.show_status("Failed to open folder. Check if the directory exists.", COLOR_WARNING)


    def render_permission_row(self, parent_frame, permission, row_index, app_id):
        """Renders a single permission row with status and toggle button."""
        
        p_frame = ttk.Frame(parent_frame, padding=8, relief='groove', borderwidth=1)
        p_frame.grid(row=row_index, column=0, sticky="ew", pady=3)
        p_frame.grid_columnconfigure(0, weight=1)

        # Permission Name and Status
        name_label = ttk.Label(p_frame, text=permission['name'], font=('Inter', 10, 'bold'))
        name_label.grid(row=0, column=0, sticky="w")
        
        status_label = ttk.Label(p_frame, text=f"Status: {permission['status']}", foreground="#6b7280")
        status_label.grid(row=1, column=0, sticky="w")

        # Toggle Button Logic
        is_enabled = permission['status'] in ('Enabled', 'Read/Write', 'Unrestricted')
        button_text = 'Revoke' if is_enabled else 'Grant'
        
        # Determine the status to toggle to
        new_status = 'Denied' if is_enabled else 'Enabled'

        # Only display toggle button if the status isn't "Unrestricted" (Native apps)
        if permission['status'] != 'Unrestricted':
            toggle_button = ttk.Button(p_frame, 
                                    text=button_text, 
                                    style='Danger.TButton' if is_enabled else 'Safe.TButton',
                                    command=partial(self.toggle_permission, app_id, permission['id'], new_status))
            toggle_button.grid(row=0, column=1, rowspan=2, padx=10, sticky="e")
        else:
            # Placeholder for Native apps where permissions can't be revoked easily
            tk.Label(p_frame, 
                     text="No Sandbox Control", 
                     fg=COLOR_DANGER, 
                     font=('Inter', 9, 'italic')).grid(row=0, column=1, rowspan=2, padx=10, sticky="e")


    def toggle_permission(self, app_id, permission_id, new_status):
        """Handles permission toggling."""
        
        success = self.app_manager.update_permission(app_id, permission_id, new_status)

        if success:
            app = next((a for a in self.app_manager.app_data if a['id'] == app_id), None)
            if app:
                self.show_app_details(app)
                self.render_app_list()
                self.show_status(f"Permission '{new_status}' for {app['name']} executed.", COLOR_SAFE if new_status == 'Enabled' else COLOR_WARNING)
        else:
            self.show_status("Error: Could not update permission. Check terminal for failure details.", COLOR_DANGER)
            
    def confirm_uninstall(self, app_name, app_id):
        """Confirms uninstallation before executing."""
        result = messagebox.askyesno(
            "Confirm Uninstall (DANGEROUS ACTION)",
            f"Are you ABSOLUTELY sure you want to uninstall {app_name}? This action will execute a real system command and is usually irreversible."
        )
        
        if result:
            self.execute_uninstall(app_name, app_id)

    def execute_uninstall(self, app_name, app_id):
        """Executes the uninstallation process."""
        
        success = self.app_manager.uninstall_app(app_id)
        
        if success:
            self.show_placeholder()
            self.render_app_list()
            self.show_status(f"Uninstall command successful for {app_name}. Check your system for confirmation.", COLOR_DANGER)
        else:
            self.show_status(f"Uninstall command FAILED for {app_name}. See terminal output.", COLOR_WARNING)


    def show_status(self, message, color):
        """Shows a temporary status message at the bottom of the window."""
        self.status_label.configure(text=message, bg=color)
        self.status_label.lift() 
        
        if hasattr(self, '_status_timer'):
            self.after_cancel(self._status_timer)
        self._status_timer = self.after(4000, lambda: self.status_label.configure(text="", bg=COLOR_SECONDARY))


if __name__ == "__main__":
    app = AppScope()
    app.mainloop()
