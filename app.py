import threading

import customtkinter as ctk

from data_load import get_departures, load_data

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class DepartureApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Karlsruhe ÖPNV Board")
        self.geometry("620x620")

        # Title Label
        self.title_label = ctk.CTkLabel(self, text="Karlsruhe Departure Board", font=("Helvetica", 22, "bold"))
        self.title_label.pack(pady=15)

        # Search Frame
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.search_frame.pack(pady=10)

        self.entry_stop = ctk.CTkEntry(self.search_frame, placeholder_text="e.g. Marktplatz", width=300, height=40, font=("Helvetica", 14))
        self.entry_stop.pack(side="left", padx=10)
        self.entry_stop.bind("<Return>", lambda event: self.handle_search())  # Enter starts the search

        self.search_button = ctk.CTkButton(self.search_frame, text="Search", command=self.handle_search, height=40, font=("Helvetica", 14, "bold"), state="disabled")
        self.search_button.pack(side="left")

        # Status line (shows "Loading..." until the data is ready)
        self.status_label = ctk.CTkLabel(self, text="Loading timetable data...", font=("Helvetica", 12))
        self.status_label.pack()

        # Scrollable Frame for Departures
        self.results_container = ctk.CTkScrollableFrame(self, width=540, height=420, corner_radius=10)
        self.results_container.pack(pady=15)

        # Load the timetable ONCE in a background thread so the window stays responsive
        self.loaded = threading.Event()
        threading.Thread(target=self._load_in_background, daemon=True).start()
        self.after(200, self._check_loaded)

    def _load_in_background(self):
        try:
            load_data()
            self.load_error = None
        except Exception as error:  # e.g. missing data files
            self.load_error = error
        self.loaded.set()

    def _check_loaded(self):
        """Runs on the GUI thread every 200 ms until the background loading has finished."""
        if not self.loaded.is_set():
            self.after(200, self._check_loaded)
            return
        if self.load_error:
            self.status_label.configure(text=f"Could not load data: {self.load_error}")
        else:
            self.status_label.configure(text="Ready")
            self.search_button.configure(state="normal")

    def handle_search(self):
        stop_name = self.entry_stop.get().strip()
        if not stop_name or not self.loaded.is_set() or self.load_error:
            return
        # Clear old rows
        for widget in self.results_container.winfo_children():
            widget.destroy()
        # Fetch station groups dictionary (fast now: only dictionary lookups)
        station_data = get_departures(stop_name)
        if not station_data:
            no_result_label = ctk.CTkLabel(self.results_container, text=f"No departures found for '{stop_name}'.", font=("Helvetica", 14))
            no_result_label.pack(pady=20)
            return
        # Loop through each distinct station found
        for station_name, departures in station_data.items():
            if not departures:
                continue

            # Station Section Header
            header_label = ctk.CTkLabel(
                self.results_container,
                text=f"📍 {station_name}",
                font=("Helvetica", 15, "bold"),
                anchor="w",
                text_color=("#1c7ed6", "#748ffc")
            )
            header_label.pack(fill="x", pady=(12, 4), padx=5)

            # Departure cards for this specific station
            for dep in departures:
                row_frame = ctk.CTkFrame(self.results_container, fg_color=("gray85", "gray20"), corner_radius=6)
                row_frame.pack(fill="x", pady=4, padx=5)

                # 1. Line Badge
                line_label = ctk.CTkLabel(row_frame, text=dep['line'], font=("Helvetica", 15, "bold"), width=45, fg_color=("#3b5bdb", "#4c6ef5"), text_color="white", corner_radius=4)
                line_label.pack(side="left", padx=10, pady=8)

                # 2. Clean Destination Name
                dest_label = ctk.CTkLabel(row_frame, text=dep['destination'], font=("Helvetica", 13), anchor="w")
                dest_label.pack(side="left", padx=5, pady=8, expand=True, fill="x")

                # 3. Departure Time
                time_label = ctk.CTkLabel(row_frame, text=dep['time'], font=("Helvetica", 14, "bold"))
                time_label.pack(side="right", padx=12, pady=8)

                # 4. Countdown Badge
                mins_label = ctk.CTkLabel(row_frame, text=f"in {dep['minutes']}m", font=("Helvetica", 12, "bold"), text_color="#2b8a3e")
                mins_label.pack(side="right", padx=5, pady=8)


if __name__ == "__main__":
    app = DepartureApp()
    app.mainloop()