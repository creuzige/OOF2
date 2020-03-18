# -*- python -*-

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

from ooflib.SWIG.common import coord
from ooflib.SWIG.common import geometry
from ooflib.SWIG.common import guitop
from ooflib.SWIG.common import lock
from ooflib.SWIG.common import progress
from ooflib.SWIG.common import switchboard
from ooflib.SWIG.common.IO.OOFCANVAS import oofcanvas
from ooflib.common import debug
from ooflib.common import mainthread
from ooflib.common import primitives
from ooflib.common import subthread
from ooflib.common import utils
from ooflib.common.IO import display
from ooflib.common.IO import gfxmanager
from ooflib.common.IO import ghostgfxwindow
from ooflib.common.IO import mainmenu
from ooflib.common.IO import reporter
from ooflib.common.IO.GUI import chooser
from ooflib.common.IO.GUI import gfxmenu
from ooflib.common.IO.GUI import gfxwindowbase
from ooflib.common.IO.GUI import gtklogger
from ooflib.common.IO.GUI import gtkutils
from ooflib.common.IO.GUI import labelledslider
from ooflib.common.IO.GUI import mousehandler
from ooflib.common.IO.GUI import quit
from ooflib.common.IO.GUI import subWindow

from gi.repository import GObject
from gi.repository import Gtk
import threading

# during_callback() is called (by CanvasOutput.show()) only in
# non-threaded mode, so we don't worry about the thread-safety of a
# global variable here.
_during_callback = 0
def during_callback():
    return _during_callback

class ContourMapData:
    # This class just aggregates data related to the ContourMap
    # display, to keep the code (relatively) tidy.
    def __init__(self):
        self.canvas = None
        self.rawdevice = None
        self.device = None
        self.mouse_down = None
        self.mark_value = None
        self.canvas_mainlayer = None
        self.canvas_ticklayer = None


#TODO: Figure out what now overlaps with gfxwindowbase and clean up.

class GfxWindow(gfxwindowbase.GfxWindowBase):
    # This whole initialization sequence is complicated. See note in
    # gfxwindowbase.py

    def preinitialize(self, name, gfxmgr, clone):
        debug.mainthreadTest()
        self.gtk = None
        self.closed = None # State data used at window-close time.
        self.name = name
        self.oofcanvas = None
        self.realized = 0
        self.zoomed = 0
        self.settings = ghostgfxwindow.GfxSettings()
        self.mouseHandler = mousehandler.nullHandler # doesn't do anything
        self.rubberband = None

        self.contourmapdata = ContourMapData()

        # Build all the GTK objects for the interior of the box.  These
        # actually get added to the window itself after the SubWindow
        # __init__ call.  They need to be created first so the
        # GhostGfxWindow can operate on them, and then create the menus
        # which are handed off to the SubWindow.
        self.mainpane = gtk.Paned(orientation=Gtk.Orientation.VERTICAL,
                                  wide_handle=True)
        gtklogger.setWidgetName(self.mainpane, 'Pane0')
        gtklogger.connect_passive(self.mainpane, 'notify::position')

        # Panes dividing upper pane horizontally into 3 parts.
        # paned1's left half contains paned2.
        self.paned1 = gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,
                                wide_handle=True)
        gtklogger.setWidgetName(self.paned1, "Pane1")
        self.mainpane.pack1(self.paned1, resize=True, shrink=True)
        gtklogger.connect_passive(self.paned1, 'notify::position')

        # paned2 is in left half of paned1
        self.paned2 = gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,
                                wide_handle=True)
        gtklogger.setWidgetName(self.paned2, "Pane2")
        self.paned1.pack1(self.paned2, resize=True, shrink=True)
        gtklogger.connect_passive(self.paned2, 'notify::position')

        # The toolbox is in the left half of paned2 (ie the left frame of 3)
        toolboxframe = gtk.Frame()
        toolboxframe.set_shadow_type(Gtk.ShadowType.IN)
        self.paned2.pack1(toolboxframe, resize=True, shrink=True)

        # Box containing the toolbox label and the scroll window for
        # the toolbox itself.
        toolboxbox1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        toolboxframe.add(toolboxbox1)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        toolboxbox1.pack_start(hbox, expand=0, fill=0, padding=2)
        hbox.pack_start(Gtk.Label("Toolbox:"), expand=0, fill=0, padding=3)
        
        self.toolboxchooser = chooser.ChooserWidget([],
                                                    callback=self.switchToolbox,
                                                    name="TBChooser")
        hbox.pack_start(self.toolboxchooser.gtk, expand=1, fill=1, padding=3)

        # Scroll window for the toolbox itself.
        toolboxbox2 = Gtk.ScrolledWindow()
        gtklogger.logScrollBars(toolboxbox2, 'TBScroll')
        
        toolboxbox2.set_policy(Gtk.PolicyType.AUTOMATIC,
                               Gtk.PolicyType.AUTOMATIC)
        toolboxbox1.pack_start(toolboxbox2, expand=1, fill=1, padding=0)

        # Actually, the tool box goes inside yet another box, so that
        # we have a gtk.VBox that we can refer to later.
        self.toolboxbody = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                   spacing=2)
        toolboxbox2.add_with_viewport(self.toolboxbody)

        self.toolboxGUIs = []           # GUI wrappers for toolboxes.
        self.current_toolbox = None

        # canvasbox contains the time slider and the canvas
        canvasbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.paned2.pack2(canvasbox, resize=True, shrink=True)

        # timebox contains widgets for displaying and setting the time
        # for all AnimationLayers in the window.
        self.timebox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                               spacing=2)
        gtklogger.setWidgetName(self.timebox, 'time')
        canvasbox.pack_start(self.timebox, expand=False, fill=False)
        self.timebox.pack_start(gtk.Label("time:"), expand=False, fill=False,
                                padding=0)
        self.prevtimeButton = gtkutils.StockButton("go-previous-symbolic")
        gtklogger.setWidgetName(self.prevtimeButton, "prev")
        gtklogger.connect(self.prevtimeButton, 'clicked', self.prevtimeCB)
        self.timebox.pack_start(self.prevtimeButton, expand=False, fill=False,
                                padding=0)
        self.prevtimeButton.set_tooltip_text("Go to the previous stored time.")
        self.nexttimeButton = gtkutils.StockButton("go-next-symbolic")
        gtklogger.setWidgetName(self.nexttimeButton, "next")
        gtklogger.connect(self.nexttimeButton, 'clicked', self.nexttimeCB)
        self.timebox.pack_start(self.nexttimeButton, expand=False, fill=False,
                                padding=0)
        self.nexttimeButton.set_tooltip_text("Go to the next stored time.")

        # The slider/entry combo has immediate==False because we don't
        # want to update until the user is done typing a time.
        self.timeslider = labelledslider.FloatLabelledSlider(
            value=0.0, vmin=0, vmax=0, step=0.01,
            callback=self.timeSliderCB,
            name='timeslider',
            immediate=False)

        # self.timeslider.set_policy(gtk.UPDATE_DISCONTINUOUS)
        self.timebox.pack_start(self.timeslider.gtk, expand=True, fill=True,
                                padding=0)
        self.timeslider.set_tooltips(
            slider="Select an interpolation time.",
            entry="Enter an interpolation time.")
        
        self.makeCanvasWidgets(gtklogger, canvasbox)
        self.makeContourMapWidgets(gtklogger)

        # HACK.  Set the position of the toolbox/canvas divider.  This
        # prevents the toolbox pane from coming up minimized.
        self.paned2.set_position(250)

        # Bottom part of main pane is a list of layers.  The actual
        # DisplayLayer objects are stored in self.display.

        layerFrame = Gtk.Frame(label='Layers')
        
        self.mainpane.pack2(layerFrame, resize=False, shrink=True)
        self.layerScroll = Gtk.ScrolledWindow()
        gtklogger.logScrollBars(self.layerScroll, "LayerScroll")
        self.layerScroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                                    Gtk.PolicyType.AUTOMATIC)
        layerFrame.add(self.layerScroll)

        self.layerList = Gtk.ListStore(GObject.TYPE_PYOBJECT)
        self.layerListView = Gtk.TreeView(self.layerList)
        gtklogger.setWidgetName(self.layerListView, "LayerList")
        self.layerListView.set_row_separator_func(self.layerRowSepFunc)
        self.layerListView.set_reorderable(True)
        self.layerListView.set_fixed_height_mode(False) # TODO GTK3: True?
        self.layerScroll.add(self.layerListView)

        gtklogger.adoptGObject(self.layerList, self.layerListView,
                              access_method=self.layerListView.get_model)

        # Handle right-clicks on the layer list.  They pop up the Layer
        # menu.
        gtklogger.connect(self.layerListView, 'button-press-event',
                          self.layerlistbuttonCB)

        # The row-deleted and row-inserted signals are used to detect
        # when the user has reordered rows manually.  When the program
        # does anything that might cause these signals to be emitted,
        # it must first call suppressRowOpSignals.
        self.rowOpSignals = [
            gtklogger.connect(self.layerList, "row-deleted",
                             self.listRowDeletedCB),
            gtklogger.connect(self.layerList, "row-inserted",
                             self.listRowInsertedCB)
            ]
        self.destination_path = None

        showcell = Gtk.CellRendererToggle()
        showcol = Gtk.TreeViewColumn("Show")
        showcol.pack_start(showcell, expand=False)
        showcol.set_cell_data_func(showcell, self.renderShowCell)
        self.layerListView.append_column(showcol)
        gtklogger.adoptGObject(showcell, self.layerListView,
                               access_function=gtklogger.findCellRenderer,
                               access_kwargs={'col':0, 'rend':0})
        gtklogger.connect(showcell, 'toggled', self.showcellCB)

        cmapcell = Gtk.CellRendererToggle()
        cmapcell.set_radio(True)
        cmapcol = gtk.TreeViewColumn("Map")
        cmapcol.pack_start(cmapcell, expand=False)
        cmapcol.set_cell_data_func(cmapcell, self.renderCMapCell)
        self.layerListView.append_column(cmapcol)
        gtklogger.adoptGObject(cmapcell, self.layerListView,
                               access_function=gtklogger.findCellRenderer,
                               access_kwargs={'col':1, 'rend':0})
        gtklogger.connect(cmapcell, 'toggled', self.cmapcellCB)        

        freezecell = Gtk.CellRendererToggle()
        freezecol = Gtk.TreeViewColumn("Freeze")
        freezecol.pack_start(freezecell, expand=False)
        freezecol.set_cell_data_func(freezecell, self.renderFreezeCell)
        self.layerListView.append_column(freezecol)
        gtklogger.adoptGObject(freezecell, self.layerListView,
                               access_function=gtklogger.findCellRenderer,
                               access_kwargs={'col':2, 'rend':0})
        gtklogger.connect(freezecell, 'toggled', self.freezeCellCB)

        layercell = Gtk.CellRendererText()
        layercol = Gtk.TreeViewColumn("What")
        layercol.set_resizable(True)
        layercol.pack_start(layercell, expand=True)
        layercol.set_cell_data_func(layercell, self.renderLayerCell)
        self.layerListView.append_column(layercol)

        methodcell = Gtk.CellRendererText()
        methodcol = Gtk.TreeViewColumn("How")
        methodcol.set_resizable(True)
        methodcol.pack_start(methodcell, expand=True)
        methodcol.set_cell_data_func(methodcell, self.renderMethodCell)
        self.layerListView.append_column(methodcol)

        gtklogger.adoptGObject(self.layerListView.get_selection(),
                              self.layerListView,
                              access_method=self.layerListView.get_selection)
        self.selsignal = gtklogger.connect(self.layerListView.get_selection(), 
                                          'changed', self.selectionChangedCB)
        gtklogger.connect(self.layerListView, 'row-activated',
                         self.layerDoubleClickCB)

    def makeCanvasWidgets(self, gtklogger, container):
        # The canvas is in the right half of paned2 (ie the middle
        # pane of 3).  We *don't* use a ScrolledWindow for it, because
        # we need direct access to the Scrollbars.  Instead, we make
        # the Scrollbars ourselves and put them in a Table with the
        # canvas.
        self.canvasTable = Gtk.Grid()
        gtklogger.setWidgetName(self.canvasTable, "Canvas")
        self.canvasTable.set_column_spacing(0)
        self.canvasTable.set_row_spacing(0)
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        frame.add(self.canvasTable)
        container.pack_start(frame, expand=True, fill=True, padding=0)
#         self.paned2.pack2(frame, resize=True)
        self.hScrollbar = Gtk.Scrollbar(orientation=Gtk.Orientation.HORIZONTAL)
        self.vScrollbar = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL)
        gtklogger.setWidgetName(self.hScrollbar, "hscroll")
        gtklogger.setWidgetName(self.vScrollbar, "vscroll")
        # Catch button release events on the Scrollbars, so that their
        # changes can be logged.  *Don't* catch the "changed" signals
        # from their Adjustments, because they occur too often.
        gtklogger.connect(self.hScrollbar, "button-release-event",
                          self.scrlReleaseCB, 'h')
        gtklogger.connect(self.vScrollbar, "button-release-event",
                          self.scrlReleaseCB, 'v')
        self.canvasTable.attach(self.hScrollbar, 0,1, 1,2)
        self.canvasTable.attach(self.vScrollbar, 1,2, 0,1)
        self.canvasFrame = Gtk.Frame()
        self.canvasFrame.set_shadow_type(Gtk.ShadowType.NONE)
        self.canvasTable.attach(self.canvasFrame, 0,1, 0,1)

    def makeContourMapWidgets(self, gtklogger):
        # the contourmap is in the right half of paned1 (the right pane of 3)
        contourmapframe = Gtk.Frame()
        contourmapframe.set_shadow_type(Gtk.ShadowType.IN)
        self.paned1.pack2(contourmapframe, resize=False, shrink=True)

        contourmapbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        gtklogger.setWidgetName(contourmapbox, "ContourMap")
        contourmapframe.add(contourmapbox)
        self.contourmap_max = Gtk.Label("max", halign=Gtk.Align.CENTER)
        gtklogger.setWidgetName(self.contourmap_max, "MapMax")
        self.new_contourmap_canvas()    # Sets self.contourmapdata.canvas.
        self.contourmap_min = Gtk.Label("min", halign=Gtk.Align.CENTER)
        gtklogger.setWidgetName(self.contourmap_min, "MapMin")
        contourmaplevelbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                     spacing=1)
        self.contourlevel_min = Gtk.Label()
        contourmaplevelbox.pack_start(self.contourlevel_min,
                                      expand=True, fill=True, padding=0)
        contourmaplevelbox.pack_start(
            gtk.Separator(orientation=Gtk.Orientation.VERTICAL),
            expand=False, fill=False, padding=0)
        contourmaplevelbox.pack_start(
            gtk.Separator(orientation=Gtk.Orientation.VERTICAL),
            expand=False, fill=False, padding=0)
        self.contourlevel_max = Gtk.Label()
        contourmaplevelbox.pack_end(self.contourlevel_max,
                                    expand=True, fill=True, padding=0)
        contourmapclearbutton = Gtk.Button("Clear Mark")
        gtklogger.setWidgetName(contourmapclearbutton, "Clear")
        gtklogger.connect(contourmapclearbutton, "clicked",
                         self.contourmap_clear_marker)
        contourmapbox.pack_start(self.contourmap_max, expand=False, fill=False,
                                 padding=0)
        contourmapbox.pack_start(
            gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            expand=False, fill=False, padding=0)
        contourmapbox.pack_start(self.contourmapdata.canvas.layout,
                                 expand=True, fill=True)
        contourmapbox.pack_start(
            Gtk.HSeparator(orientation=Gtk.Orientation.HORIZONTAL),
            expand=False, fill=False, padding=0)
        contourmapbox.pack_start(self.contourmap_min, expand=False, fill=False,
                                 padding=0)
        contourmapbox.pack_start(
            gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            expand=False, fill=False, padding=0)
        contourmapbox.pack_start(
            gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            expand=False, fill=False, padding=0)
        contourmapbox.pack_start(contourmaplevelbox, expand=False, fill=False,
                                 padding=0)
        contourmapbox.pack_start(
            gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            expand=False, fill=False, padding=0)
        contourmapbox.pack_end(contourmapclearbutton, expand=False, fill=False,
                               padding=0)
        contourmapframe.show_all()


    def postinitialize(self, name, gfxmgr, clone):
        debug.mainthreadTest()
        # Add gui callbacks to the non-gui menu created by the GhostGfxWindow.
        filemenu = self.menu.File
        filemenu.Quit.add_gui_callback(quit.queryQuit)
        layermenu = self.menu.Layer
        layermenu.New.add_gui_callback(self.newLayer_gui)
        layermenu.Edit.add_gui_callback(self.editLayer_gui)
        layermenu.Delete.add_gui_callback(self.deleteLayer_gui)
        layermenu.Hide.add_gui_callback(self.hideLayer_gui)
        layermenu.Show.add_gui_callback(self.showLayer_gui)
        layermenu.Freeze.add_gui_callback(self.freezeLayer_gui)
        layermenu.Unfreeze.add_gui_callback(self.unfreezeLayer_gui)
        layermenu.Hide_Contour_Map.add_gui_callback(
            self.hideLayerContourmap_gui)
        layermenu.Show_Contour_Map.add_gui_callback(
            self.showLayerContourmap_gui)
        layermenu.Raise.One_Level.add_gui_callback(self.raiseLayer_gui)
        layermenu.Raise.To_Top.add_gui_callback(self.raiseToTop_gui)
        layermenu.Lower.One_Level.add_gui_callback(self.lowerLayer_gui)
        layermenu.Lower.To_Bottom.add_gui_callback(self.lowerToBottom_gui)
        settingmenu = self.menu.Settings
        toolboxmenu = self.menu.Toolbox

        # Construct gui's for toolboxes.  This must be done after the
        # base class is constructed so that all non-gui toolboxes are
        # created before any of their gui versions.  Some gui
        # toolboxes need to know about more than one non-gui toolbox.
        
        map(self.makeToolboxGUI, self.toolboxes)
        if self.toolboxGUIs:
            self.selectToolbox(self.toolboxGUIs[0].name())
            self.toolboxchooser.set_state(self.toolboxGUIs[0].name())

        # raise_window routine is in SubWindow class.
        getattr(mainmenu.OOF.Windows.Graphics, name).add_gui_callback(
            self.raise_window)

        # SubWindow initializer makes the menu bar, and sets up the
        # .gtk and .mainbox members.  ".gtk" is the window itself,
        # and .mainbox is a gtk.VBox that holds the menu bar.
        windowname = utils.underscore2space("OOF2 " + name)
        subWindow.SubWindow.__init__(
            self, windowname, menu=self.menu)

        # # Create the popup menu for the layer list.
        # self.layerpopup = gfxmenu.gtkOOFPopUpMenu(self.menu.Layer,
        #                                           self.layerListView)


        self.gtk.connect('destroy', self.destroyCB)
        self.gtk.connect_after('realize', self.realizeCB)
        self.gtk.set_default_size(ghostgfxwindow.GhostGfxWindow.initial_width,
                                  ghostgfxwindow.GhostGfxWindow.initial_height)

        self.mainbox.set_spacing(3)

        self.mainbox.pack_start(self.mainpane, fill=1, expand=1)

        self.gtk.show_all()

        self.updateToolboxChooser()
        self.switchboardCallbacks.append(
            switchboard.requestCallback("shutdown", self.shutdownCB))

    def __repr__(self):
        return 'GfxWindow("%s")' % self.name

    ################################################

    def newCanvas(self):
        # Create the canvas object.
        # It's important to acquire and release the lock in the
        # subthread, before calling mainthread.runBlock, to avoid
        # deadlocks.
        debug.subthreadTest()
        self.acquireGfxLock()
        try:
            mainthread.runBlock(self.newCanvas_thread)
        finally:
            self.releaseGfxLock()

    def newCanvas_thread(self):
        debug.mainthreadTest()
        assert self.oofcanvas is None
        ## TODO GTK3: How to set initial size of the Canvas?
        self.oofcanvas = oofcanvas.OOFCanvas(width=300, height=300, ppu=1.0,
                                             vexpand=True, hexpand=True)
        self.oofcanvas.antialias(self.settings.antialias)
##        self.oofcanvas = fakecanvas.FakeCanvas(self.settings.antialias)
        self.canvasFrame.add(self.oofcanvas.layout)
        self.hScrollbar.set_adjustment(self.oofcanvas.get_hadjustment())
        self.vScrollbar.set_adjustment(self.oofcanvas.get_vadjustment())
        # Changes to the adjustments need to go into the gui log.
        gtklogger.adoptGObject(self.hScrollbar.get_adjustment(),
                               self.hScrollbar,
                               access_method=self.hScrollbar.get_adjustment)
        gtklogger.adoptGObject(self.vScrollbar.get_adjustment(),
                               self.vScrollbar,
                               access_method=self.vScrollbar.get_adjustment)
        gtklogger.connect_passive(self.hScrollbar.get_adjustment(),
                                  'value-changed')
        gtklogger.connect_passive(self.vScrollbar.get_adjustment(),
                                  'value-changed')

        ## TODO GTK3: Get GUI logging working with the new OOFCanvas.
        
        # # GUI logging stuff.
        # canvasroot = self.oofcanvas.rootitem()
        # init_canvas_logging(canvasroot) # one-time initialization
        # # Although canvasroot is a gtk widget, it's not a pygtk
        # # widget, which makes life difficult.  So here it's adopted by
        # # a pygtk widget instead, and uses various hacks to get itself
        # # logged.  The actual widget doing the adopting is completely
        # # arbitrary since it will be passed as the first argument of
        # # findCanvasRoot, which discards it.  It does have to be a
        # # loggable pygtk widget, though, because
        # # AdopteeLogger.location() doesn't know that it will be
        # # discarded.  I did say that this is a hack, didn't I?
        # gtklogger.adoptGObject(canvasroot, self.canvasTable,
        #                        access_function=findCanvasRoot,
        #                        access_kwargs={"windowname":self.name})
        # gtklogger.connect_passive(canvasroot, "event")

        # if ppu is not None:
        #     self.oofcanvas.set_pixels_per_unit(ppu)
        #     self.oofcanvas.set_scrollregion(scrollregion)
        #     self.oofcanvas.set_scroll_offsets(offsets)

        # delayed import to avoid import loops
        from ooflib.common.IO.GUI import canvasoutput
        from ooflib.common.IO import outputdevice

        # Use the buffered device.
        rawdevice = canvasoutput.CanvasOutput(self.oofcanvas)
        self.device = outputdevice.BufferedOutputDevice(rawdevice)

        # # On a new canvas, these should both be set at once,
        # # since they both need to call underlay.
        # self.oofcanvas.set_underlay_params(
        #     self.settings.bgcolor, self.settings.margin)

        self.oofcanvas.setBackgroundColor(self.settings.bgcolor.red(),
                                          self.settings.bgcolor.green(),
                                          self.settings.bgcolor.blue())
        ## TODO GTK3: margin
        # self.oofcanvas.setMargin(self.settings.margin)

        self.oofcanvas.setMmouseCallback(self.mouseCB)
        if self.rubberband:
            self.oofcanvas.set_rubberband(self.rubberband)
        self.oofcanvas.show()

        self.fix_step_increment()


    # Contour map stuff.
    ###########################################

    # Create object and assign to self.contourmap_canvas.
    def new_contourmap_canvas(self):
        debug.mainthreadTest()
        if self.contourmapdata.canvas:
            self.contourmapdata.canvas.destroy()

        # Argument is ppu.  TODO GTK3: Does the value here matter?
        # Just call zoomToFill after drawing.
        self.contourmapdata.canvas = oofcanvas.OOFCanvas(
            100, self.oofcanvas.heightInPixels(), 1)
        self.contourmapdata.canvas.setBackgroundColor(
            self.settings.bgcolor.red(),
            self.settings.bgcolor.green(),
            self.settings.bgcolor.blue())

        # Duplicate imports, again to avoid an import loop.
        from ooflib.common.IO.GUI import canvasoutput
        from ooflib.common.IO import outputdevice
        
        self.contourmapdata.rawdevice=canvasoutput.CanvasOutput(
            self.contourmapdata.canvas)
        self.contourmapdata.device=outputdevice.BufferedOutputDevice(
            self.contourmapdata.rawdevice)
        
        self.contourmapdata.canvas.setResizeCallback(
            self.contourmap_resize)
        self.contourmapdata.canvas.setMouseCallback(self.contourmap_mouse, None)

        # Create two layers, one for the "main" drawing, and
        # one for the ticks.
        self.contourmapdata.canvas_mainlayer = \
                               self.contourmapdata.device.begin_layer("main")
        self.contourmapdata.canvas_ticklayer = \
                               self.contourmapdata.device.begin_layer("tick")
        self.contourmapdata.canvas_ticklayer.raise_to_top()
    
##    # Function called after layers have been arranged.  Does not
##    # draw the actual contourmap, just records the layers.
##    def contourmap_newlayers(self):
##        ghostgfxwindow.GhostGfxWindow.contourmap_newlayers(self)
##        for ell in self.display:
##            if ell==self.current_contourmap_method:
##                mainthread.runBlock(
##                    self.layerwidgets[ell].setContourmapButton,(1,))
##            else:
##                mainthread.runBlock(
##                    self.layerwidgets[ell].setContourmapButton,(0,))

    # def set_contourmap_layer(self, method):
    #     ghostgfxwindow.GhostGfxWindow.set_contourmap_layer(self, method)
        
            
    # Draw the contourmap onto the canvas, and update the numbers on the
    # display.  Called after all the layers have been drawn in the
    # main pane.  Also called from the menu callback which resets the
    # aspect ratio.

    # TODO LATER: There is some clunkiness in this routine, associated
    # particularly with the "discrete" displays, most particularly
    # with the CenterFill display.  The problem is that, in the
    # center-fill display and the skeleton quality display, the colors
    # drawn on the main canvas are broad swaths painted with the color
    # corresponding to a particular level, which behaves as a "contour
    # level" -- when there are few of these, this looks dumb, some
    # colors which may occur over a wide area of the main canvas will
    # be invisible on the contourmap.  This problem occurs for regular
    # contours also, but isn't as noticeable, partially because you
    # have more of them, and partially because the maximum of a real
    # contour plot occupies a small fraction of the main-canvas area.
    
    # A possible answer is to make the colormap be drawn continuously,
    # no matter how many levels their actually are.  Alternatively,
    # one could figure out how to do something sensible with the fact
    # that contour lines in general occur at particular levels, but if
    # you want to see something on the map, it has to be drawn over an
    # interval.

    # Called on a subthread now, but that's OK, device is buffered.
    def show_contourmap_info(self):
        if not self.gtk:
            return

        ## TODO: Should the rest of this function be inside the "if
        ## current_contourmap_method:" block?  That would cut down on
        ## a lot of the extraneous "contourmap info updated"
        ## checkpoints in the gui logs.

        self.contourmapdata.canvas_mainlayer.removeAllItems()
        #self.contourmapdata.canvas_mainlayer.make_current()
        
        c_min = None
        c_max = None

        # Copy self.current_contourmap_method to a local variable to
        # prevent interference from other threads.
        current_contourmethod = self.current_contourmap_method

        ## TODO: There are an awful lot of mainthread.runBlock calls
        ## here, which is probably quite inefficient.  Can they be
        ## consolidated?

        if current_contourmethod:
            current_contourmethod.draw_contourmap(
                self, self.contourmapdata.device)
            (c_min, c_max, lvls) = \
                    current_contourmethod.get_contourmap_info()


            # Flush the buffered device, so geometry data is valid.
            self.contourmapdata.device.flush_wait()
            
            # Zoom and scroll the canvas so that the drawn contour map 
            # exactly fills it vertically.
            ph = mainthread.runBlock(
                self.contourmapdata.canvas.get_height_in_pixels)

            # c_max can equal c_min....
            if c_max!=c_min:
                ppu = 1.0*ph/abs(c_max-c_min)
            else:
                ppu = ph  # Arbitrary, one unit for all the pixels.

            ## TODO GTK3: This has to be done completely differently
            ## for OOFCanvas.  There's no scrollregion to be set, and
            ## the ppu will be computed automatically.

            # Set the scrollregion and pixels-per-unit in the right
            # order.  If the new ppu is much larger than then old ppu,
            # the memory required by the canvas will explode unless
            # the new scrollregion set first.  It's also necessary to
            # call canvas.underlay() at the right time, so that a
            # large underlayer isn't drawn with a high ppu.
            oldppu = mainthread.runBlock(
                self.contourmapdata.canvas.get_pixels_per_unit)
            if ppu > oldppu:            # new map is smaller in physical units
                mainthread.runBlock(self.contourmapdata.canvas.underlay)
                # Recompute bounds *after* recomputing the underlayer,
                # because the old underlayer is too big, and is
                # included in the bounds computation.
                bounds = mainthread.runBlock(
                    self.contourmapdata.canvas.get_bounds)
                mainthread.runBlock(
                    self.contourmapdata.canvas.set_scrollregion, (bounds,))
                # Now that the canvas is only drawing small things,
                # it's ok to set ppu to something big.
                mainthread.runBlock(
                    self.contourmapdata.canvas.set_pixels_per_unit, (ppu,))
            else:           # ppu < oldppu, new map is larger in phyical units
                mainthread.runBlock(
                    self.contourmapdata.canvas.set_pixels_per_unit, (ppu,))
                bounds = mainthread.runBlock(
                    self.contourmapdata.canvas.get_bounds)
                mainthread.runBlock(
                    self.contourmapdata.canvas.set_scrollregion, (bounds,))
                mainthread.runBlock(
                    self.contourmapdata.canvas.underlay)

        self.contourmapdata.device.end_layer()
        self.contourmapdata.device.show()
        
        if c_min is None:
            mainthread.runBlock(
                self.contourmap_min.set_text, ('min',))
        else:
            mainthread.runBlock(
                self.contourmap_min.set_text,
                ( ("%.3g" % c_min).rstrip(), ) )
            
        if c_max is None:
            mainthread.runBlock(
                self.contourmap_max.set_text, ('max',) )
        else:
            mainthread.runBlock(
                self.contourmap_max.set_text,
                ( ("%.3g" % c_max).rstrip(), ) )

        self.show_contourmap_ticks(self.contourmapdata.mark_value)
        gtklogger.checkpoint("contourmap info updated for " + self.name)


    # Draw the marks on it.  Argument is the new value for the ticks.
    # A tick-layer redraw can be forced by setting
    # self.contourmapdata.mark_value to None and then calling this with
    # the new value.
    def show_contourmap_ticks(self, y):
        if not self.gtk:
            return
        c_min = None
        c_max = None
        
        if self.current_contourmap_method:
            (c_min, c_max, lvls) = \
                    self.current_contourmap_method.get_contourmap_info()

        if ((c_max is not None) and (c_min is not None)):
            if y is not None:
                real_y = y + c_min
                # need to know which level am I in.
                level = None
                for i in range(len(lvls)):
                    if real_y <= lvls[i]:
                        level = i-1
                        if i==len(lvls):
                            i -= 1
                        break
                if level is not None:
                    self.contourmapdata.canvas_ticklayer.clear()
                    self.contourmapdata.canvas_ticklayer.raise_to_top()
                    self.contourmapdata.canvas_ticklayer.make_current()
                
                    self.contourmapdata.device.set_lineColor(
                        self.settings.contourmap_markercolor)
                    self.contourmapdata.device.set_lineWidth(
                        self.settings.contourmap_markersize)
                    width=(c_max-c_min)/self.settings.aspectratio

                    polygon = primitives.Polygon(
                        [primitives.Point(0.0, lvls[level]-c_min),
                         primitives.Point(width, lvls[level]-c_min),
                         primitives.Point(width, lvls[level+1]-c_min),
                         primitives.Point(0.0, lvls[level+1]-c_min)
                         ])
                    self.contourmapdata.device.draw_polygon(polygon)

                    self.contourmapdata.mark_value = y
                    minimum = lvls[level]
                    maximum = lvls[level] + (lvls[1]-lvls[0])
                    mainthread.runBlock(
                        self.contourlevel_min.set_text,
                        ("%.2e" % minimum,) )
                    mainthread.runBlock(
                        self.contourlevel_max.set_text,
                        ("%.2e" % maximum,) )

        # If any of the above conditions were not met, clear the
        # tick layer.
        if (c_max is None) or (c_min is None) or \
               (y is None) or (level is None):
            self.contourmapdata.canvas_ticklayer.clear()
            mainthread.runBlock(
                self.contourlevel_min.set_text, ('',) )
            mainthread.runBlock(
                self.contourlevel_max.set_text, ('',) )

        self.contourmapdata.device.show()

    # Callback for size changes of the pane containing the contourmap.
    def contourmap_resize(self):
        self.contourmapdata.canvas.zoomToFill()
        # debug.mainthreadTest()
        # if self.current_contourmap_method:
        #     (c_min, c_max, c_lvls) = \
        #             self.current_contourmap_method.get_contourmap_info()
        #     if c_max!=c_min:
        #         ppu = 1.0*height/(c_max-c_min)
        #         # ppu = 1.0*height/1000.0
        #     else:
        #         ppu = height # Arbitrary

        #     # ppu changes here can't be large, so we don't have to
        #     # worry about order of operations (see comment in
        #     # show_contourmap_info, above).
        #     self.contourmapdata.canvas.set_pixels_per_unit(ppu)
        #     self.contourmapdata.canvas.set_scrollregion(
        #         self.contourmapdata.canvas.get_bounds())

    def contourmap_mouse(self, event, x, y, button, shift, ctrl, data):
        debug.mainthreadTest()
        if event=="down":
            self.contourmapdata.mouse_down = 1
        elif (event=="move") and self.contourmapdata.mouse_down==1:
            subthread.execute(self.show_contourmap_ticks, (y,))
        elif event=="up":
            self.contourmapdata.mouse_down = None
            subthread.execute(self.show_contourmap_ticks, (y,))

    # Button callback.
    def contourmap_clear_marker(self, gtk):
        self.contourmapdata.mark_value = None
        self.contourlevel_min.set_text('')
        self.contourlevel_max.set_text('')
        subthread.execute(self.show_contourmap_info)

    # Overridden menu callbacks for the contourmap show/hide menu item.
    def hideLayerContourmap(self, menuitem, n):
        self.acquireGfxLock()
        try:
            ghostgfxwindow.GhostGfxWindow.hideLayerContourmap(self, menuitem, n)
            self.layerListRowChanged(n)
            self.show_contourmap_info()
        finally:
            self.releaseGfxLock()
        
    def showLayerContourmap(self, menuitem, n):
        self.acquireGfxLock()
        try:
            ghostgfxwindow.GhostGfxWindow.showLayerContourmap(self, menuitem, n)
            self.layerListRowChanged(n)
            self.show_contourmap_info()
        finally:
            self.releaseGfxLock()

    
    # GUI callbacks -- required because the GUI menu item must
    # operate on the current layer.
    def hideLayerContourmap_gui(self, menuitem):
        if self.selectedLayer is None:
            reporter.report(
                "Unable to hide contour map, no layer is selected.")
        else:
            menuitem(n=self.layerID(self.selectedLayer))

    def showLayerContourmap_gui(self, menuitem):
        if self.selectedLayer is None:
            reporter.report(
                "Unable to show contour map, no layer is selected.")
        else:
            menuitem(n=self.layerID(self.selectedLayer))

                
    # Called on a subthread, not on the main thread.
    # Argument is actually used at gfxwindow-open-time by the menu command.
    def draw(self, zoom=False): # switchboard "redraw" callback
        debug.subthreadTest()
        if self.closed:
            return
        if self.oofcanvas.is_empty():
            # *Always* zoom to fill the window on the first non-trivial draw
            zoom = True

            ## OOFCanvas shouldn't have this problem:
            # # Some drawing operations (canvasdot and canvastriangle in
            # # particular) require pixels_per_unit to be set *before*
            # # they're drawn.  This is a problem for the initial
            # # drawing, so here we just guess at the best value, and
            # # set ppu.  Since the canvas will be zoomed soon, it
            # # doesn't matter if the value isn't quite correct.
            # topwho = self.topwho("Microstructure", "Image",
            #                      "Skeleton", "Mesh")
            # if topwho:
            #     topms = topwho.getMicrostructure()
            #     width, height = topms.size()
            #     bbox = geometry.CRectangle(coord.Coord(0.0, 0.0),
            #                                coord.Coord(width, height))
            #     mainthread.runBlock(self.zoom_bbox)
        self.acquireGfxLock()
        try:
            self.updateTimeControls()
            self.display.draw(self, self.device)
            self.device.flush_wait() # needed when animating and zooming
            if zoom and self.realized:
                self.zoomFillWindow(lock=False)
        finally:
            self.releaseGfxLock()
        # Update the contourmap info, now that the appropriate layer
        # has completed its draw.
        self.show_contourmap_info()
            
###########

    ## TODO MAYBE: when looping, save frames as canvas groups on first
    ## pass, and show/hide groups on subsequent passes.  This probably
    ## isn't worth the effort since most of this code will go away
    ## when we switch the 2D graphics to vtk.

    def animate(self, menuitem, start, finish, times, frame_rate, style):
        menuitem.disable()
        prog = progress.getProgress("Animation", style.getProgressStyle())

        # Construct a generator that produces the times of the
        # animation frames.  Python generators aren't thread safe in
        # some mysterious way, so the generator has to be constructed
        # on the main thread.  If this isn't done, then interrupting
        # an animation can lead to an internal python error or seg
        # fault. (TODO: Check that this is still true.)
        timegen = mainthread.runBlock(self._timegenerator,
                                      (style, times, start, finish))
        # Get the full list of times from the animation layers so we
        # can find the start and finish times.  This is just to
        # calibrate the progress bar.  timegen is what actually
        # produces the frame times.
        times = self.findAnimationTimes()
        
        if times and times[-1] > times[0]:
            time0 = times[0]
            time1 = times[-1]
            # Animation timing is controlled by a timeout callback
            # which periodically sets an "escapement" Event.  Every
            # time the Event is set, it allows one frame to be drawn.
            self._escapement = threading.Event()

            # This menuitem shouldn't finish until the escapement
            # timeout callback has been cleared, which is indicated by
            # another event.
            escapementDone = threading.Event()

            # _stopAnimation indicates that the animation is complete,
            # either because it ran to the end, the user interrupted
            # it, or the program is quitting.
            self._stopAnimation = False

            # Start the escapement.
            GObject.timeout_add(
                int(1000./frame_rate), # time between frames, in milliseconds
                self._escapementCB,
                prog,
                escapementDone)

            # Draw frames, after waiting for an escapement event.
            while not self._stopAnimation:
                self._escapement.wait()
                if prog.stopped() or self._stopAnimation:
                    self._stopAnimation = True
                    break
                # Clear the event, so that we have to wait for the
                # escapement to set it again before drawing the
                # next frame. This is done *before* drawing the
                # current frame, because if drawing a frame takes
                # longer than the time between escapement events,
                # we'll want to start on the next frame as soon as
                # possible.
                self._escapement.clear()

                try:
                    time = timegen.next()
                except StopIteration:
                    self._stopAnimation = True
                else:
                    # Update the progress bar and actually do the drawing.
                    prog.setMessage(`time`)
                    prog.setFraction((time-time0)/(time1-time0))
                    self.drawAtTime(time)

            ## TODO: Use some other scheme for unthreaded mode.

            escapementDone.wait()
            prog.finish()
            menuitem.enable()

    def _escapementCB(self, prog, escapementDone):
        # Timeout callback that calls self._escapement.set()
        # periodically.  This is called on the main thread.
        self._escapement.set()
        if prog.stopped() or self._stopAnimation:
            self._stopAnimation = True
            escapementDone.set()
            return False        # don't reinstall time out callback
        return True             # do reinstall timeout callback

    def _timegenerator(self, style, times, start, finish):
        return iter(style.getTimes(times.times(start, finish, self)))

###################

    def shutdownCB(self):
        self.device.destroy()
        self._stopAnimation = True
        # self._escapement might not exist if the window hasn't
        # been animated, so we need to use try/except.
        try:  
            self._escapement.set()
        except:
            pass

###################

    # TODO: clean up the rest of this file!

    # menu callback
    def toggleAntialias(self, menuitem, antialias):
        ghostgfxwindow.GhostGfxWindow.toggleAntialias(
            self, menuitem, antialias)
        mainthread.runBlock(self.oofcanvas.antialias, (antialias,))

    # used by viewertoolbox zoom functions -- only 2D!
    def zoomFactor(self):
        return self.settings.zoomfactor

    def zoomIn(self, *args):
        self.acquireGfxLock()
        try:
            if self.oofcanvas and not self.oofcanvas.is_empty():
                mainthread.runBlock(self.oofcanvas.zoom,
                                    (self.settings.zoomfactor,))
                mainthread.runBlock(self.fix_step_increment)
                self.zoomed = 1
        finally:
            self.releaseGfxLock()

    def zoomInFocussed(self, menuitem, focus):
        self.acquireGfxLock()
        try:
            if self.oofcanvas and not self.oofcanvas.is_empty():
                mainthread.runBlock(self.oofcanvas.zoomAbout,
                                    (self.settings.zoomfactor, focus))
                mainthread.runBlock(self.fix_step_increment)
                self.zoomed = 1
        finally:
            self.releaseGfxLock()

    def zoomOut(self, *args):
        self.acquireGfxLock()
        try:
            if self.oofcanvas and not self.oofcanvas.is_empty():
                mainthread.runBlock(self.oofcanvas.zoom,
                                    (1./self.settings.zoomfactor,))
                mainthread.runBlock(self.fix_step_increment)
                self.zoomed = 1
        finally:
            self.releaseGfxLock()
        hadj = self.hScrollbar.get_adjustment()

    def zoomOutFocussed(self, menuitem, focus):
        self.acquireGfxLock()
        try:
            if self.oofcanvas and not self.oofcanvas.is_empty():
                mainthread.runBlock(self.oofcanvas.zoomAbout,
                                    (1./self.settings.zoomfactor, focus))
                mainthread.runBlock(self.fix_step_increment)
                self.zoomed = 1
        finally:
            self.releaseGfxLock()


    def zoomFillWindow_thread(self):
        debug.mainthreadTest()
        if self.closed:
            return
        if self.oofcanvas and not self.oofcanvas.is_empty():
            self.zoom_bbox()


    def zoom_bbox(self):
        debug.mainthreadTest()
        self.oofcanvas.zoomToFill()
        # width = self.oofcanvas.get_width_in_pixels()-1
        # height = self.oofcanvas.get_height_in_pixels()-1
        # if bbox.width() > 0 and bbox.height() > 0:
        #     xf = width/bbox.width()
        #     yf = height/bbox.height()
        #     ppu = min(xf, yf)       # pixels per unit
        #     oldppu = self.oofcanvas.get_pixels_per_unit()
        #     if ppu > oldppu:    # See comment in show_contourmap_info().
        #         self.oofcanvas.set_scrollregion(bbox)
        #         self.oofcanvas.set_pixels_per_unit(ppu)
        #     else:
        #         self.oofcanvas.set_pixels_per_unit(ppu)
        #         self.oofcanvas.set_scrollregion(bbox)
        #     self.zoomed = 1
        self.fix_step_increment()

    # only 2D - fix the step increment of the canvas table scroll bars
    def fix_step_increment(self):
        # For some reason, the step_increment on the canvas scroll
        # bars is zero, so the scroll arrows don't work.  This fixes
        # that.
        ## TODO GTK3: Is this still necessary?
        debug.mainthreadTest()
        hadj = self.hScrollbar.get_adjustment()
        if hadj.step_increment == 0.0:
            hadj.step_increment = hadj.page_increment/16
        vadj = self.vScrollbar.get_adjustment()
        if vadj.step_increment == 0.0:
            vadj.step_increment = vadj.page_increment/16

    # are these ever called?
##     def set_zoom(self, scrollreg, ppu):
##         self.acquireGfxLock()
##         try:
##             mainthread.runBlock(self.set_zoom_thread, (scrollreg, ppu))
##         finally:
##             self.releaseGfxLock()

##     def set_zoom_thread(self, scrollreg, ppu):
##         debug.mainthreadTest()
##         oldppu = self.oofcanvas.get_pixels_per_unit()
##         if ppu > oldppu:            # See comment in show_contourmap_info().
##             self.oofcanvas.set_scrollregion(scrollreg)
##             self.oofcanvas.set_pixels_per_unit(ppu)
##         else:
##             self.oofcanvas.set_pixels_per_unit(ppu)
##             self.oofcanvas.set_scrollregion(scrollreg)
##         self.zoomed = 1

    # GUI override of menu callback for new contourmap aspect ratio.
    # GUI callbacks are required because, when the settings change,
    # you have to redraw the window.
    def aspectRatio(self, menuitem, ratio):
        self.acquireGfxLock()
        try:
            self.settings.aspectratio = ratio
        finally:
            self.releaseGfxLock()
        self.show_contourmap_info()

    # Overridden menu callbacks for these settings.
    def contourmapMarkSize(self, menuitem, width):
        self.acquireGfxLock()
        try:
            self.settings.contourmap_markersize = width
            v = self.contourmapdata.mark_value
            self.contourmapdata.mark_value = None
        finally:
            self.releaseGfxLock()
        self.show_contourmap_ticks(v)

    def contourmapMarkColor(self, menuitem, color):
        self.acquireGfxLock()
        try:
            self.settings.contourmap_markercolor = color
            v = self.contourmapdata.mark_value
            self.contourmapdata.mark_value = None
        finally:
            self.releaseGfxLock()
        self.show_contourmap_ticks(v)

    def toggleLongLayerNames(self, menuitem, longlayernames):
        self.acquireGfxLock()
        try:
            self.settings.longlayernames = longlayernames
            self.fillLayerList()
        finally:
            self.releaseGfxLock()
        
    # Sets background color for both canvases.
    def bgColor(self, menuitem, color):          # OOFMenu callback
        self.acquireGfxLock()
        try:
            ghostgfxwindow.GhostGfxWindow.bgColor(self, menuitem, color)
            self.oofcanvas.setBackgroundColor(
                color.red(), color.green(), color.blue())
            self.contourmapdata.canvas.setBackgroundColor(
                color.red(), color.green(), color.blue())
            mainthread.runBlock(self.oofcanvas.draw)
            mainthread.runBlock(self.contourmapdata.canvas.draw)
            # mainthread.runBlock(self.oofcanvas.set_bgColor, (color,))
            # mainthread.runBlock(self.contourmapdata.canvas.set_bgColor,
            #                     (color,))
        finally:
            self.releaseGfxLock()

    def marginCB(self, menuitem, fraction):
        self.acquireGfxLock()
        try:
            self.settings.margin = fraction
            self.oofcanvas.setMargin(fraction)
        finally:
            self.releaseGfxLock()

    # Scrolling 
    ##########################################################

    def scrlReleaseCB(self, scrollbar, event, which):
        if which == 'h':
            self.menu.Settings.Scroll.Horizontal(
                position=scrollbar.get_adjustment().get_value())
        else:
            self.menu.Settings.Scroll.Vertical(
                position=scrollbar.get_adjustment().get_value())

    def hScrollCB(self, menuitem, position): # OOFMenu callback
        ghostgfxwindow.GhostGfxWindow.hScrollCB(self, menuitem, position)
        mainthread.runBlock(
            self.hScrollbar.get_adjustment().set_value, (position,))

    def vScrollCB(self, menuitem, position): # OOFMenu callback
        ghostgfxwindow.GhostGfxWindow.vScrollCB(self, menuitem, position)
        mainthread.runBlock(
            self.vScrollbar.get_adjustment().set_value, (position,))

    def hScrollPosition(self):
        return self.hScrollbar.get_adjustment().value

    def vScrollPosition(self):
        return self.vScrollbar.get_adjustment().value

    # Rubberband
    #########################################################

    def setRubberband(self, rubberband):
        self.rubberband = rubberband
        if rubberband is not None:
            self.oofcanvas.set_rubberband(rubberband)
        else:
            self.oofcanvas.removeRubberBand()

    # Right click on layer list
    #########################################################
    def layerlistbuttonCB(self, gtkobj, event):
        if event.button == 3:
            popupMenu = Gtk.Menu()
            for item in self.Menu.Layer:
                item.construct_gui(self.Menu.Layer, popupMenu, None)
            popupMenu.show_all();
            popupMenu.popup_at_pointer(event)

        # It's important to return False here, since doing so allows
        # other handlers to see the event.  In particular, it allows a
        # right-click to select the treeview line, so that the popup
        # menu can act on it.  Most of the menu items act on the
        # current selection.  [SAL: I don't quite understand the order
        # of events (no pun intended) here, but the code seems to
        # work.  layerpopup.popup() is being called *before* the
        # selection callbacks, so why is the menu sensitized
        # correctly?]
        return False         
        

    #######################

    # Time Controls. 

    ## TODO: What happens if the user types in a time that's outside
    ## of the range?

    def timeSliderCB(self, slider, val):
        self.menu.Settings.Time.callWithDefaults(time=val)
        
    def prevtimeCB(self, gtkbutton):
        times = self.findAnimationTimes()
        for i,t in enumerate(times[1:]):
            if t >= self.displayTime:
                # i indexes times[1:] so the previous time is
                # times[i], not times[i-1].
                self.menu.Settings.Time.callWithDefaults(time=times[i])
                return

    def nexttimeCB(self, gtkbutton):
        times = self.findAnimationTimes()
        for t in times:
            if t > self.displayTime:
                self.menu.Settings.Time.callWithDefaults(time=t)
                return

    def updateTimeControls(self):
        mainthread.runBlock(self._updateTimeControls)
    def _updateTimeControls(self):
        debug.mainthreadTest()
        times = self.findAnimationTimes()
        if times:
            self.timeslider.set_sensitive(True)
            mintime = min(times)
            maxtime = max(times)
            self.timeslider.setBounds(mintime, maxtime)
        else:
            self.timeslider.set_sensitive(False)
        self.sensitizeTimeButtons(times)

    def sensitizeTimeButtons(self, times=None):
        debug.mainthreadTest()
        if times is None:       # distinguish from []!
            times = self.findAnimationTimes()
        notlast = bool(times and self.displayTime != times[-1])
        notfirst = bool(times and self.displayTime != times[0])
        self.nexttimeButton.set_sensitive(notlast)
        self.prevtimeButton.set_sensitive(notfirst)

    def setTimeCB(self, menuitem, time):
        self.drawAtTime(time)

    def drawAtTime(self, time, zoom=False):
        debug.subthreadTest()
        if time is not None:
            self.setDisplayTime(time)
            mainthread.runBlock(self.timeslider.set_value, (self.displayTime,))
            # Ensure that animatable layers will be redrawn by backdating
            # them, and then calling "draw".  All time-dependent layers
            # are animatable, and they get their time from the GfxWindow's
            # displayTime.

            # Don't backdate layers that have already been drawn at the
            # given time.  Layers that have been drawn already return
            # outOfTime==True.
            for layer in self.display.layers:
                if layer.animatable(self) and layer.outOfTime(self):
                    layer.backdate(self.device)
        self.draw(zoom=zoom)

        mainthread.runBlock(self.sensitizeTimeButtons)

###########################################

# ## Support for logging and replaying mouse clicks.

# # Although the Canvas *is* a gtk Widget, it's not a pygtk Widget, and
# # it's hard to use the widget logging machinery directly on it. So we
# # pretend that it's some other kind of gtk object and use the
# # adoptGObject machinery instead.  It's adopted by
# # GfxWindow.canvasTable.  adoptGObject is told the name of the window.
# # The log uses the window name and findCanvasRoot to retrieve the
# # Canvas's root, which is the crucial bit for emitting signals.

# def findCanvasRoot(gtkobj, windowname):

#     # In gui logs, returns the root object of the canvas of the given
#     # gfxwindow.  Put into the logs by AdopteeLogger.location, via
#     # CanvasLogger.location.  See GfxWindow.newCanvas().
    
#     window = gfxmanager.gfxManager.getWindow(windowname)
#     return window.oofcanvas.rootitem()

# def findCanvasGdkWindow(windowname):
#     window = gfxmanager.gfxManager.getWindow(windowname)
#     return window.oofcanvas.widget().window

# # desired_events is a list of all of the event types that should be
# # logged on the canvas.

# desired_events = [gtk.gdk.BUTTON_PRESS,
#                   gtk.gdk.BUTTON_RELEASE,
#                   gtk.gdk.MOTION_NOTIFY]

# _canvaslogging_initialized = False

# def init_canvas_logging(canvasgroup):
#     global _canvaslogging_initialized
#     if _canvaslogging_initialized:
#         return
#     _canvaslogging_initialized = True

#     # Inject findCanvasRoot into the gtklogger replay namespace, which
#     # is where gui scripts are run.
#     gtklogger.replayDefine(findCanvasRoot)
#     gtklogger.replayDefine(findCanvasGdkWindow)

#     # The GtkLogger for Canvas events has to be defined *after* the
#     # first canvas has been created, because the GnomeCanvasGroup
#     # class isn't in pygtk.  We snag the object returned by
#     # OOFCanvas::rootitem and use its class for the CanvasLogger.
#     class CanvasLogger(gtklogger.adopteelogger.AdopteeLogger):
#         classes = (canvasgroup.__class__,)
#         def location(self, object, *args):
#             self.windowname = object.oofparent_access_kwargs['windowname']
#             return super(CanvasLogger, self).location(object, *args)
#         buttonup = True
#         def record(self, object, signal, *args):
#             if signal == "event":
#                 event = args[0]
#                 if event.type in desired_events:
#                     # event.type.value_name is something of the form
#                     # GDK_XXXXXX, but the python variable is
#                     # gtk.gdk.XXXXXX, so we have to strip off the
#                     # "GDK_".
#                     eventname = event.type.value_name[4:]
#                     if event.type in (gtk.gdk.BUTTON_PRESS,
#                                       gtk.gdk.BUTTON_RELEASE):
#                         CanvasLogger.buttonup = (event.type ==
#                                                  gtk.gdk.BUTTON_RELEASE)
#                         return [
#                             "canvasobj = %s" % self.location(object, *args),
#                             "canvasobj.emit('event', event(gtk.gdk.%s,x=%20.13e,y=%20.13e,button=%d,state=%d,window=findCanvasGdkWindow('%s')))"
#                             % (eventname, event.x, event.y, event.button,
#                                event.state, self.windowname)
#                             ]
#                     if event.type == gtk.gdk.MOTION_NOTIFY:
#                         # If the mouse is down, ignore the
#                         # suppress_motion_events flag.  Always log
#                         # mouse-down motion events, and log all motion
#                         # events if they're not suppressed.
#                         if (gtklogger.suppress_motion_events(object) and
#                             self.buttonup):
#                             return self.ignore
#                         return [
#                             "canvasobj = %s" % self.location(object, *args),
#                             "canvasobj.emit('event', event(gtk.gdk.MOTION_NOTIFY,x=%20.13e,y=%20.13e,state=%d,window=findCanvasGdkWindow('%s')))"
#                         % (event.x, event.y, event.state, self.windowname)
                    
#                         ]
#                 return self.ignore      # silently ignore other events
#             super(CanvasLogger, self).record(object, signal, *args)

##############################################

# This function redefines the one in GfxWindowManager when the GUI
# code is loaded.

def _newWindow(self, name, **kwargs):
    if guitop.top(): # if in GUI mode
        return GfxWindow(name, self, **kwargs)
    return ghostgfxwindow.GhostGfxWindow(name, self, **kwargs)

gfxmanager.GfxWindowManager._newWindow = _newWindow

