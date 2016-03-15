import tkinter.ttk
import tkinter
import sqlite3
from PIL import Image, ImageTk
from os import walk


# Manage the label that provides suggestions
class SuggestionLabel(tkinter.ttk.Label):
    def __init__(self, parent, suggestions, **kwargs):
        self.suggestions = suggestions
        tkinter.ttk.Label.__init__(self, parent, **kwargs)
        self.display_suggestions()

    # Load a list of suggestion and then display them
    # Limited to 10 suggestions
    def update_suggestions(self, new_suggestions):
        self.suggestions = new_suggestions[0:3]
        self.display_suggestions()

    # Create and display a string that contains suggestions numbered
    # 1 2 3 4 5 6 7 8 9 0 to correspond with keyboard layout
    def display_suggestions(self):
        suggestion_string = ''.join([str((i+1) % 10) + "  " + (str(x) + '\n\n')
                                     for i, x in enumerate(self.suggestions)])
        if suggestion_string == '':
            suggestion_string = 'no suggestions'
        self.config(text=suggestion_string)

    # Return a suggestion specified by an index
    # index 0 1 2 3 4 5 6 7 8 9 will return suggestion
    #       1 2 3 4 5 6 7 8 9 0
    def get_suggestion(self, index):
        return self.suggestions[index]


# Manage row highlighting and setting and clearing the Entry widget
class EntryRow:
    def __init__(self, left_highlight, entry, right_highlight):
        self.left_highlight = left_highlight
        self.entry = entry
        self.right_highlight = right_highlight
        self.activeColour = "magenta4"
        self.dormantColour = "plum1"
        self.active(False)

    # Change the row highlighting colours
    def active(self, active):
        if active:
            self.left_highlight.configure(background=self.activeColour)
            self.right_highlight.configure(background=self.activeColour)
        else:
            self.left_highlight.configure(background=self.dormantColour)
            self.right_highlight.configure(background=self.dormantColour)

    # Clear text in the entry widget
    def clear(self):
        self.entry.delete(0, tkinter.END)

    # Set text in the entry widget
    def set(self, text):
        self.clear()
        self.entry.insert(0, text)


# Main Frame that contains the application
class MainApplication(tkinter.ttk.Frame):
    def __init__(self, parent):
        # Initialise variables
        self.numberOfEntryFields = 10
        self.currentRecord = 0
        self.currentEntryField = 0
        self.image = None
        self.photo = None
        self.recordPosition = 0
        self.suggestion_search = []
        self.image_aspect_locked = True

        # When changing records set focus to first entry box
        self.rehome_entry_focus = True

        # Initialise frame
        tkinter.ttk.Frame.__init__(self, parent)
        self.grid(column=0, row=0, sticky="nsew")
        self.parent = parent
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        self.parent.title("soylentOCR")
        self.configure(height=400, width=600)
        self.grid_propagate(False)

        # Get a list of files to process from a directory
        self.directoryName = "images"
        self.recordList = []
        for (directoryPath, directoryNames, fileNames)\
                in walk(self.directoryName):
            self.recordList.extend(fileNames)
            break
        self.numberOfRecords = len(self.recordList)

        # Connect to the database.  If it doesn't exist it is created
        # Create a table for the table if it doesn't exist
        self.db_name = 'results.db'
        self.db_connection = sqlite3.connect(self.db_name)
        self.db_connection.execute('''CREATE TABLE IF NOT EXISTS RESULTS
        (FILE_NAME TEXT NOT NULL,
        ATTRIBUTE_NUMBER INT NOT NULL,
        ATTRIBUTE TEXT,
        PRIMARY KEY (FILE_NAME, ATTRIBUTE_NUMBER)
        );''')
        self.db_connection.commit()

        # Initialize a timer.  This is used to refresh the image to a high
        # quality version after the window is re-sized
        self.refresh_delay = 1000
        self.refreshTimer = self.after(self.refresh_delay,
                                       self.refresh_image,
                                       1)
        self.after_cancel(self.refreshTimer)

        # Initialise image frame
        self.image_frame = tkinter.ttk.Frame(self)
        self.image_frame.grid_propagate(False)
        self.image_label = tkinter.Label(self.image_frame, image=self.photo)
        self.image_label.image = self.photo
        self.image_label.grid(row=0, column=0, sticky="nwse")

        # Initialise entry frame
        self.entry_frame = tkinter.ttk.Frame(self)
        self.entry_frame.configure(width=200)
        self.entry_frame.grid_propagate(False)

        # Highlights an entry filed are stored in an EntryRow object
        self.entry_rows = []
        for i in range(0, self.numberOfEntryFields):

            # Tkinter string variables to use as text variables on the Entry
            # widget.  When typing in an entry widget self.entry_changed()
            # is called.
            entry_string_variable = tkinter.StringVar()
            entry_string_variable.trace("w",
                                        lambda _name1,
                                        _name2,
                                        _mode,
                                        sv=entry_string_variable:
                                        self.entry_changed(sv))
            entry = tkinter.ttk.Entry(self.entry_frame,
                                      textvariable=entry_string_variable)

            # This creates a coloured highlight either side of the entry widget
            # to show the active Entry box
            left_highlight = tkinter.ttk.Label(self.entry_frame, text=" ")
            right_highlight = tkinter.ttk.Label(self.entry_frame, text=" ")

            # Allow the entry field to horizontally
            # fill empty space in the frame
            left_highlight.grid(row=i, column=0)
            entry.grid(row=i, column=1, sticky="e w")
            right_highlight.grid(row=i, column=2)

            # Create FocusIn and FocusOut events for all entry fields
            entry.bind("<FocusIn>",
                       lambda event,
                       row_number=i: self.entry_focus_in(event, row_number))
            entry.bind("<FocusOut>",
                       lambda event,
                       row_number=i: self.entry_focus_out(event, row_number))

            # Configure spacing
            self.entry_frame.grid_rowconfigure(i, weight=1)
            self.entry_frame.grid_columnconfigure(i, pad=0)

            # Keep track of all the rows in a list
            # rows are numbered starting with zero to be consistent with
            # zero based indexing of lists
            row = EntryRow(left_highlight, entry, right_highlight)
            self.entry_rows.append(row)

        # Allow the entry column to expand
        self.entry_frame.columnconfigure(0, weight=0)
        self.entry_frame.columnconfigure(1, weight=1)
        self.entry_frame.columnconfigure(2, weight=0)

        # Initialise the suggestion frame
        self.suggestion_frame = tkinter.ttk.Frame(self)
        self.suggestion_frame.configure(width=200)
        self.suggestion_frame.grid_propagate(False)

        # Configure suggestion label
        self.suggestion_label = SuggestionLabel(self.suggestion_frame,
                                                [],
                                                text="test2")
        self.suggestion_label.grid(row=0, column=0)

        # Bind Control modified number keys - may not work on macs
        for i in range(10):
            self.parent.bind("".join("<Control-Key-" + str(i) + ">"),
                             self.pick_suggestion)

        # Bind Enter key to enable selection of first option
        self.parent.bind("<Return>", self.pick_suggestion)

        # Bind Shift-Delete to clear the entry box
        self.parent.bind("<Shift-Delete>", self.clear_entry)

        # Initialise status frame
        self.status_frame = tkinter.ttk.Frame(self)
        self.status_frame.configure(height=80)
        self.status_frame.grid_propagate(False)
        self.status_label = tkinter.ttk.Label(self.status_frame,
                                              text="",
                                              background='light blue',
                                              anchor='nw')
        self.status_frame.rowconfigure(0, weight=1)
        self.status_frame.columnconfigure(0, weight=1)
        self.status_label.grid(in_=self.status_frame,
                               column=0,
                               row=0,
                               sticky='nsew')

        # Key events
        self.parent.bind("<Down>", self.down_pressed)
        self.parent.bind("<Up>", self.up_pressed)
        self.image_frame.bind("<Configure>", self.image_frame_resize)

        # Order of image, entry, suggestion and status frames
        self.image_frame.grid(column=0, row=0, sticky="nwse", rowspan=2)
        self.entry_frame.grid(column=1, row=0, sticky="ns", rowspan=2)
        self.suggestion_frame.grid(column=2, row=0, sticky='ns')
        self.status_frame.grid(column=2, row=1, sticky='ew')

        # Column padding between image, entry and search frames
        # Allow row zero and column zero to resize
        self.columnconfigure(0, pad=10, weight=1)
        self.columnconfigure(1, pad=10, weight=0)
        self.columnconfigure(2, pad=10, weight=0)
        self.rowconfigure(0, weight=1)

        # Display current record
        self.display_record()

        # Give focus to an entry box
        self.change_entry_offset(0)

    # Clear the currently selected entry box
    def clear_entry(self, event):
        if event.keycode == 46:
            self.entry_rows[self.currentEntryField].clear()

    # Set the current Entry Field to a suggestion selected with the
    # key combination of control + <number>
    def pick_suggestion(self, event):

        # If enter key is pressed select first suggestion
        if event.keycode == 13:
            index = 1
        else:
            index = (event.keycode-49) % 10 + 1

        try:
            self.entry_rows[self.currentEntryField].\
                set(self.suggestion_label.get_suggestion(index - 1))
        except IndexError as e:
            # If a suggestion that doesn't exist is selected, just ignore it
            pass

    # Method to handle the callback from the tkinter StringVar associated with
    # the Entry boxes
    def entry_changed(self, sv):
        self.refresh_suggestions()

    # Update the suggestion frame.  Called when text in entry box is changed or
    # a different entry box gets focus
    def refresh_suggestions(self):
        temporary_suggestions = []

        # Gets the text in the current entry box and splits it into words based
        # on locations of spaces
        current_search = self.entry_rows[self.currentEntryField].\
            entry.get().split()

        # If entry box is empty all suggestions all valid
        if len(current_search) == 0:
            temporary_suggestions = self.suggestion_search
        else:
            for suggestion in self.suggestion_search:
                # Test each suggestion to see if it contains all
                # the words in current_search
                if all(word in suggestion for word in current_search):
                    temporary_suggestions.append(suggestion)

        self.suggestion_label.update_suggestions(temporary_suggestions)

    # Move focus to another Entry box by supplying an offset.  This is done in
    # a circular fashion through number of entry boxes
    def change_entry_offset(self, offset):
        self.currentEntryField += offset
        self.currentEntryField %= self.numberOfEntryFields
        self.entry_rows[self.currentEntryField].entry.focus()

    # Move focus to another Entry box by supplying an absolute index.  This is
    # wrapped around if an index that is too high is supplied
    def change_entry_absolute(self, index):
        self.currentEntryField = index
        self.currentEntryField %= self.numberOfEntryFields
        self.entry_rows[self.currentEntryField].entry.focus()

    # When an Entry box gets focus, change the program state and activate
    # the Entry box
    def entry_focus_in(self, event, row_number):
        self.currentEntryField = row_number
        self.entry_rows[row_number].active(True)
        self.refresh_suggestions()

    # When an Entry loses focus, deactivate the Entry box
    def entry_focus_out(self, event, row_number):
        self.entry_rows[row_number].active(False)

    # If the up key is pressed move to the Entry box above the current one
    def up_pressed(self, event):
        self.change_entry_offset(-1)

    # If the down key is pressed move to the Entry box below the current one
    def down_pressed(self, event):
        self.change_entry_offset(1)

    # When the tab key is pressed go forward or back one record.
    # Direction depends on if the shift key is depressed.
    def tab_pressed(self, event):
        # The first step is to bind the tab key to an ignore function.  This
        # prevents it interrupting the program flow if it's pressed in quick
        # succession.
        self.parent.bind("<Tab>", self.ignore_press)

        # For reference, event.state is a treated as a binary register that
        # indicates if modifier keys are pressed.  The lowest bit indicates
        # the shift key
        is_shift_pressed = event.state % 2
        if is_shift_pressed:
            self.change_record(-1)
        else:
            self.change_record(1)
        return 'break'

    # A function to bind a key to so that presses have no effect
    def ignore_press(self, event):
        return 'break'

    # Take the values from the entry boxes and write them to the database
    def save_current_entries(self):
        for index, row in enumerate(self.entry_rows):
            file_name = self.recordList[self.currentRecord]
            record = (file_name, str(index), row.entry.get())
            self.db_connection.execute(
                "INSERT OR REPLACE INTO RESULTS values (?, ?, ?)", record)
            self.db_connection.commit()

        # Clear the entry boxes
        for row in self.entry_rows:
            row.clear()

    # Changes the currently displayed record by an offset
    def change_record(self, offset):
        self.save_current_entries()
        self.currentRecord += offset
        self.currentRecord %= self.numberOfRecords
        self.display_record()

    # load a new record from file and database
    def display_record(self):
        image_error_string = ''
        attribute_error_string = ''

        # Attempt to load each file as an image. If it isn't an image of pure
        # red colour is used
        try:
            self.image = Image.open("".
                                    join(self.directoryName +
                                         "/" +
                                         self.recordList[self.currentRecord]))
        except OSError as e:
            image_error_string = "\nNot a recognised image file"
            self.image = Image.new("RGB", (512, 512), "red")

        # Get the attributes associated with a particular record
        file_name = self.recordList[self.currentRecord]
        cursor = self.db_connection.execute('''SELECT ATTRIBUTE_NUMBER,
                                            ATTRIBUTE from RESULTS
                                            where FILE_NAME=?''', (file_name,))

        # Load the attributes into the entry boxes.  If there are not enough
        # entry boxes, show an error message.
        for attribute in cursor:
            try:
                self.entry_rows[attribute[0]].set(attribute[1])
            except IndexError as e:
                attribute_error_string = ''.join("\nRecord has more than " +
                                                 str(self.numberOfEntryFields) +
                                                 " attributes")

        # Get all possible attributes values from the database.  These are
        # returned in descending order of how often they appear in the database
        cursor = self.db_connection.execute('''SELECT ATTRIBUTE from
                                            RESULTS GROUP BY ATTRIBUTE
                                            ORDER BY COUNT(ATTRIBUTE) DESC''')

        # Turn cursor into a list, ignoring empty ('') attributes
        self.suggestion_search = [i[0] for i in cursor.fetchall()]
        self.suggestion_search = [i for i in self.suggestion_search if i != '']

        # Construct a status string and display it
        status_string = ''.join('File name: ' +
                                self.recordList[self.currentRecord] +
                                '\nProgress: ' +
                                str(self.currentRecord + 1) +
                                ' / ' +
                                str(self.numberOfRecords) +
                                image_error_string +
                                attribute_error_string)
        self.status_label.configure(text=status_string)

        # Update the image with a high quality version
        self.refresh_image(1)

        # Move focus to the first entry box
        if self.rehome_entry_focus:
            self.change_entry_absolute(0)

        # Reactivate the tab key
        self.parent.bind("<Tab>", self.tab_pressed)

    # When the image frame is re-sized, change
    # the size of the label that contains the image
    def image_frame_resize(self, event):
        image_frame_height = self.image_frame.winfo_height()
        image_frame_width = self.image_frame.winfo_width()
        self.image_label.configure(height=image_frame_height,
                                   width=image_frame_width)

        # Display and resize current image.  When the user resizes the window
        # this method is called often.  Resizing the image this much creates
        # lag.  A timer is cancelled and created every time this is called with
        # a delay of x milliseconds.  This means that x milliseocnds after this
        # method is called for the last time, a high quality antialiased
        # refresh of the image occurs.  Otherwise a low quality image resize
        # occurs when the window is being dynamically resized to eliminate lag.
        self.after_cancel(self.refreshTimer)
        self.refreshTimer = self.after(self.refresh_delay,
                                       self.refresh_image,
                                       1)  # 1 indicates high quality

        # Low quality refresh
        self.refresh_image(0)

    # Resize the image and display it. Aspect can be locked. Quality can be
    # high or low
    def refresh_image(self, quality):
            try:
                image_width, image_height = self.image.size
                frame_width = self.image_frame.winfo_width()
                frame_height = self.image_frame.winfo_height()

                if self.image_aspect_locked:
                    width_ratio = image_width / frame_width
                    height_ratio = image_height / frame_height
                    resize_ratio = max(width_ratio, height_ratio)
                    new_width = int(image_width/resize_ratio)
                    new_height = int(image_height/resize_ratio)
                else:
                    new_width = frame_width
                    new_height = frame_height

                if quality == 1:
                    image2 = self.image.resize((new_width, new_height),
                                               Image.ANTIALIAS)
                else:
                    image2 = self.image.resize((new_width, new_height))

                self.photo = ImageTk.PhotoImage(image2)
                self.image_label.configure(image=self.photo, anchor="center")
                self.image_label.configure(background="white")

            except AttributeError:
                pass


# Manage closing the program cleanly
def close_program(root_window, frame):
    frame.save_current_entries()

    # Destroy needs to be explicitly called
    root_window.destroy()

if __name__ == "__main__":
    root = tkinter.Tk()
    main_frame = MainApplication(root)
    root.protocol("WM_DELETE_WINDOW", lambda: close_program(root, main_frame))
    root.mainloop()
