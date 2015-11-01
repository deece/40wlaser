import sys

def app():
    import Tkinter
    app = Tkinter.Tk(className='emcRasterEngrave')
    app.withdraw()
    return app

def image_not_found():
    import tkFileDialog, tkMessageBox
    app()
    name = tkFileDialog.askopenfilename(title='Raster Image',
	initialfile='',
	filetypes=[('Images',('*.png', '*.gif', '*.jpg', '*.tif', '*.bmp')),
	           ('Any File', '*.*')])
    if not name:
	sys.exit(2)
    return name


def fatal(msg):
    import tkMessageBox
    app()
    tkMessageBox.showerror(title='Raster Engrave Error', message=msg)
    sys.exit(2)

