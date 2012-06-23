#!/usr/bin/python
#
# cam.py
#
# Neil Gershenfeld
#
# (c) Massachusetts Institute of Technology 2006
# Permission granted for experimental and personal use;
# license for commercial sale available from MIT.
#
DATE = "10/2/06"

prompt = \
"""modes: 1D path following, 2D contour and raster, 3D slicing
input:
   *.svg: SVG (polylines and paths)
   *.dxf: DXF (2D polylines, 3D polymeshes)
   *.stl: STL (binary and ASCII)
   *.cmp,*.sol,*.via,*.mill: Gerber
      RS-274X format, with 0-width trace defining board boundary
   *.drl, *.drd: Excellon (with embedded drill defitions)
   *.jpg: z bitmap
output:
   *.rml: Roland Modela RML mill
   *.camm: Roland CAMM cutter
   *.jpg,*.bmp: images
   *.epi: Epilog lasercutter
   *.uni: Universal lasercutter
   *.g: G codes
   *.ord: OMAX waterjet cutter
   *.oms: Resonetics excimer micromachining center
   *.dxf: DXF
   *.stl: STL
keys: Q to quit
usage: python cam.py [[-i] infile][-d display scale][-p part scale][-x xmin][-y ymin][-o outfile][-f force][-v velocity][-t tooldia][-a rate][-e power][-s speed][-h height][-c contour][-r raster][-n no noise][-# number of arc segments][-j jobname][-w write toolpath]
"""

from Tkinter import *
from tkFileDialog import *
from string import *
from math import *
from random import *
from struct import *
import os
import sys, Image, ImageDraw

#
# window size in pixels
#
WINDOW = 500
#
# numerical roundoff tolerance for testing intersections
#
EPS = 1e-20
#
# relative std dev of numerical noise to add to remove degeneracies
#
NOISE = 1e-6
noise_flag = 1

HUGE = 1e10

X = 0
Y = 1
Z = 2
INTERSECT = 2
INDEX = 2
EDGE = 2
X3 = 0
Y3 = 1
Z3 = 3

DOWN = 0
UP = 1
DIRECTION = 2

START = 0
END = 1
EVENT_SEG = 3
EVENT_VERT = 4

SEG = 0
VERT = 1
A = 1
DINTERSECT = 2
XINTERSECT = 3
YINTERSECT = 4
IINTERSECT = 5

TYPE = 0
SIZE = 1
WIDTH = 1
HEIGHT = 2

def coord(str,digits,fraction):
   #
   # parse Gerber coordinates
   #
   global gerbx, gerby
   xindex = find(str,"X")
   yindex = find(str,"Y")
   index = find(str,"D")
   if (xindex == -1):
      x = gerbx
      y = int(str[(yindex+1):index])*(10**(-fraction))
   elif (yindex == -1):
      y = gerby
      x = int(str[(xindex+1):index])*(10**(-fraction))
   else:
      x = int(str[(xindex+1):yindex])*(10**(-fraction))
      y = int(str[(yindex+1):index])*(10**(-fraction))
   gerbx = x
   gerby = y
   return [x,y]

def read_Gerber(filename):
   global boundarys
   #
   # Gerber parser
   #
   file = open(filename,'r')
   str = file.readlines()
   file.close()
   segment = -1
   xold = []
   yold = []
   line = 0
   nlines = len(str)
   boundary = []
   macros = []
   N_macros = 0
   apertures = [[] for i in range(1000)]
   while line < nlines:
      if (find(str[line],"%FS") != -1):
         #
         # format statement
         #
         index = find(str[line],"X")
         digits = int(str[line][index+1])
         fraction = int(str[line][index+2])
         line += 1
         continue
      elif (find(str[line],"%AM") != -1):
         #
         # aperture macro
         #
         index = find(str[line],"%AM")
         index1 = find(str[line],"*")
         macros.append([])
         macros[-1] = str[line][index+3:index1]
         N_macros += 1
         line += 1
         continue
      elif (find(str[line],"%MOIN*%") != -1):
         #
	 # inches
	 #
	 line += 1
	 continue
      elif (find(str[line],"G01*") != -1):
         #
	 # linear interpolation
	 #
	 line += 1
	 continue
      elif (find(str[line],"G70*") != -1):
         #
	 # inches
	 #
	 line += 1
	 continue
      elif (find(str[line],"G75*") != -1):
         #
	 # circular interpolation
	 #
	 line += 1
	 continue
      elif (find(str[line],"%ADD") != -1):
         #
         # aperture definition
         #
         index = find(str[line],"%ADD")
         parse = 0
         if (find(str[line],"C,") != -1):
            #
            # circle
            #
            index = find(str[line],"C,")
            index1 = find(str[line],"*")
            aperture = int(str[line][4:index])
            size = float(str[line][index+2:index1])
            apertures[aperture] = ["C",size]
            print "   read aperture",aperture,": circle diameter",size
            line += 1
            continue
         elif (find(str[line],"O,") != -1):
            #
            # obround
            #
            index = find(str[line],"O,")
            aperture = int(str[line][4:index])
            index1 = find(str[line],",",index)
            index2 = find(str[line],"X",index)
            index3 = find(str[line],"*",index)
            width = float(str[line][index1+1:index2])
            height = float(str[line][index2+1:index3])
            apertures[aperture] = ["O",width,height]
            print "   read aperture",aperture,": obround",width,"x",height
            line += 1
            continue
         elif (find(str[line],"R,") != -1):
            #
            # rectangle
            #
            index = find(str[line],"R,")
            aperture = int(str[line][4:index])
            index1 = find(str[line],",",index)
            index2 = find(str[line],"X",index)
            index3 = find(str[line],"*",index)
            width = float(str[line][index1+1:index2])
            height = float(str[line][index2+1:index3])
            apertures[aperture] = ["R",width,height]
            print "   read aperture",aperture,": rectangle",width,"x",height
            line += 1
            continue
         for macro in range(N_macros):
            #
            # macros
            #
            index = find(str[line],macros[macro]+',')
            if (index != -1):
               #
      	       # hack: assume macros can be approximated by
   	       # a circle, and has a size parameter
	       #
  	       aperture = int(str[line][4:index])
	       index1 = find(str[line],",",index)
	       index2 = find(str[line],"*",index)
	       size = float(str[line][index1+1:index2])
	       apertures[aperture] = ["C",size]
	       print "   read aperture",aperture,": macro (assuming circle) diameter",size
	       parse = 1
	       continue
	    if (parse == 0):
	       print "   aperture not implemented:",str[line]
	       return
      elif (find(str[line],"D01*") != -1):
         #
         # pen down
         #
         [xnew,ynew] = coord(str[line],digits,fraction)
         line += 1
         if (size > EPS):
            if ((abs(xnew-xold) > EPS) | (abs(ynew-yold) > EPS)):
               newpath = stroke(xold,yold,xnew,ynew,size)
               boundary.append(newpath)
               segment += 1
         else:
            boundary[segment].append([xnew,ynew,[]])
         xold = xnew
         yold = ynew
         continue
      elif (find(str[line],"D02*") != -1):
         #
         # pen up
         #
         [xold,yold] = coord(str[line],digits,fraction)
         if (size < EPS):
            boundary.append([])
            segment += 1
            boundary[segment].append([xold,yold,[]])
         newpath = []
         line += 1
         continue
      elif (find(str[line],"D03*") != -1):
         #
         # flash
         #
	 if (find(str[line],"D03*") == 0):
	    #
	    # coordinates on preceeding line
	    #
	    [xnew,ynew] = [xold,yold]
	 else:
	    #
	    # coordinates on this line
	    #
            [xnew,ynew] = coord(str[line],digits,fraction)
         line += 1
         if (apertures[aperture][TYPE] == "C"):
            #
            # circle
            #
            boundary.append([])
            segment += 1	
            size = apertures[aperture][SIZE]
            for i in range(nverts):
               angle = i*2.0*pi/(nverts-1.0)
               x = xnew + (size/2.0)*cos(angle)
               y = ynew + (size/2.0)*sin(angle)
     	       boundary[segment].append([x,y,[]])
         elif (apertures[aperture][TYPE] == "R"):
            #
            # rectangle
            #
            boundary.append([])
            segment += 1	
            width = apertures[aperture][WIDTH] / 2.0
            height = apertures[aperture][HEIGHT] / 2.0
            boundary[segment].append([xnew-width,ynew-height,[]])
            boundary[segment].append([xnew+width,ynew-height,[]])
            boundary[segment].append([xnew+width,ynew+height,[]])
            boundary[segment].append([xnew-width,ynew+height,[]])
            boundary[segment].append([xnew-width,ynew-height,[]])
         elif (apertures[aperture][TYPE] == "O"):
            #
            # obround
            #
            boundary.append([])
            segment += 1	
            width = apertures[aperture][WIDTH]
            height = apertures[aperture][HEIGHT]
            if (width > height):
               for i in range(nverts/2):
                  angle = i*pi/(nverts/2-1.0) + pi/2.0
                  x = xnew - (width-height)/2.0 + (height/2.0)*cos(angle)
                  y = ynew + (height/2.0)*sin(angle)
  	          boundary[segment].append([x,y,[]])
               for i in range(nverts/2):
                  angle = i*pi/(nverts/2-1.0) - pi/2.0
                  x = xnew + (width-height)/2.0 + (height/2.0)*cos(angle)
                  y = ynew + (height/2.0)*sin(angle)
	          boundary[segment].append([x,y,[]])
            else:
               for i in range(nverts/2):
                  angle = i*pi/(nverts/2-1.0) + pi
                  x = xnew + (width/2.0)*cos(angle)
                  y = ynew - (height-width)/2.0 + (width/2.0)*sin(angle)
 	          boundary[segment].append([x,y,[]])
               for i in range(nverts/2):
                  angle = i*pi/(nverts/2-1.0)
                  x = xnew + (width/2.0)*cos(angle)
                  y = ynew + (height-width)/2.0 + (width/2.0)*sin(angle)
	          boundary[segment].append([x,y,[]])
            boundary[segment].append(boundary[segment][0])
         else:
            print "   aperture",apertures[aperture][TYPE],"is not implemented"
            return
         xold = xnew
         yold = ynew
         continue
      elif (find(str[line],"D") == 0):
         #
         # change aperture
         #
         index = find(str[line],'*')
         aperture = int(str[line][1:index])
         size = apertures[aperture][SIZE]
         line += 1
         continue
      elif (find(str[line],"G54D") == 0):
         #
         # change aperture
         #
         index = find(str[line],'*')
         aperture = int(str[line][4:index])
         size = apertures[aperture][SIZE]
         line += 1
         continue
      else:
         print "   not parsed:",str[line]
      line += 1
   boundarys[0] = boundary

def read_Excellon(filename):
   global boundarys
   #
   # Excellon parser
   #
   file = open(filename,'r')
   str = file.readlines()
   file.close()
   segment = -1
   line = 0
   nlines = len(str)
   boundary = []
   header = TRUE
   drills = [[] for i in range(1000)]
   while line < nlines:
      if ((find(str[line],"T") != -1) & (find(str[line],"C") != -1) \
         & (find(str[line],"F") != -1)):
         #
         # alternate drill definition style
         #
         index = find(str[line],"T")
         index1 = find(str[line],"C")
         index2 = find(str[line],"F")
         drill = int(str[line][1:index1])
         print str[line][index1+1:index2]
         size = float(str[line][index1+1:index2])
         drills[drill] = ["C",size]
         print "   read drill",drill,"size:",size
         line += 1
         continue
      if ((find(str[line],"T") != -1) & (find(str[line]," ") != -1) \
         & (find(str[line],"in") != -1)):
         #
         # alternate drill definition style
         #
         index = find(str[line],"T")
         index1 = find(str[line]," ")
         index2 = find(str[line],"in")
         drill = int(str[line][1:index1])
         print str[line][index1+1:index2]
         size = float(str[line][index1+1:index2])
         drills[drill] = ["C",size]
         print "   read drill",drill,"size:",size
         line += 1
         continue
      elif ((find(str[line],"T") != -1) & (find(str[line],"C") != -1)):
         #
         # alternate drill definition style
         #
         index = find(str[line],"T")
         index1 = find(str[line],"C")
         drill = int(str[line][1:index1])
         size = float(str[line][index1+1:-1])
         drills[drill] = ["C",size]
         print "   read drill",drill,"size:",size
         line += 1
         continue
      elif (find(str[line],"T") == 0):
         #
         # change drill
         #
         index = find(str[line],'T')
         drill = int(str[line][index+1:-1])
         size = drills[drill][SIZE]
         line += 1
         continue
      elif (find(str[line],"X") != -1):
         #
         # drill location
         #
         index = find(str[line],"X")
         index1 = find(str[line],"Y")
         x0 = float(int(str[line][index+1:index1])/10000.0)
         y0 = float(int(str[line][index1+1:-1])/10000.0)
         line += 1
         boundary.append([])
         segment += 1	
         size = drills[drill][SIZE]
         for i in range(nverts):
            angle = -i*2.0*pi/(nverts-1.0)
            x = x0 + (size/2.0)*cos(angle)
            y = y0 + (size/2.0)*sin(angle)
            boundary[segment].append([x,y,[]])
         continue
      else:
         print "   not parsed:",str[line]
      line += 1
   boundarys[0] = boundary

def read_STL(filename):
   global vertices, faces, boundarys, noise_flag
   #
   # STL parser
   #
   noise_flag = 0
   vertex = 0
   vertices = []
   faces = []
   boundarys = []
   file = open(filename,'rb')
   str = file.read()
   file.close()
   if (find(str,"vertex") != -1):
      #
      # ASCII file
      #
      print "   ASCII file"
      file = open(filename,'r')
      str = file.readlines()
      file.close()
      line = 0
      nlines = len(str)
      while (line < nlines):
	 if (find(str[line],'vertex') != -1):
	    [vert, x, y, z] = split(str[line])
	    x1 = float(x)
	    y1 = float(y)
	    z1 = float(z)
  	    vertices.append([x1,y1,z1])
	    vertex += 1
	    line += 1
	    [vert, x, y, z] = split(str[line])
	    x2 = float(x)
	    y2 = float(y)
	    z2 = float(z)
  	    vertices.append([x2,y2,z2])
	    vertex += 1
	    line += 1
	    [vert, x, y, z] = split(str[line])
	    x3 = float(x)
	    y3 = float(y)
	    z3 = float(z)
  	    vertices.append([x3,y3,z3])
	    vertex += 1
#	    faces.append([vertex-2,vertex-1,vertex,vertex-2])
	    faces.append([vertex-2,vertex-1,vertex])
	 line += 1
   else:
      #
      # binary file
      #
      nfacets = (len(str)-84)/50
      print "   binary file with",nfacets,"facets"
      for facet in range(nfacets):
         index = 84 + facet*50
	 x1 = unpack('f',str[index+12:index+16])[0]
	 y1 = unpack('f',str[index+16:index+20])[0]
	 z1 = unpack('f',str[index+20:index+24])[0]
	 vertices.append([x1,y1,z1])
	 vertex += 1
	 x2 = unpack('f',str[index+24:index+28])[0]
	 y2 = unpack('f',str[index+28:index+32])[0]
	 z2 = unpack('f',str[index+32:index+36])[0]
	 vertices.append([x2,y2,z2])
	 vertex += 1
	 x3 = unpack('f',str[index+36:index+40])[0]
	 y3 = unpack('f',str[index+40:index+44])[0]
	 z3 = unpack('f',str[index+44:index+48])[0]
	 vertices.append([x3,y3,z3])
	 vertex += 1
#	 faces.append([vertex-2,vertex-1,vertex,vertex-2])
	 faces.append([vertex-2,vertex-1,vertex])

def read_DXF(filename):
   global vertices, faces, boundarys
   #
   # DXF parser
   #
   file = open(filename,'r')
   str = file.readlines()
   file.close()
   segment = -1
   boundary = []
   vertices = []
   faces = []
   boundarys = []
   xold = []
   yold = []
   nlines = len(str)
   dim = 2
   for line in range(len(str)-1):
      #
      # check for 3D file
      #
      if ((strip(str[line]) == "70") & (strip(str[line+1]) == "192")):
         print "   found polyface mesh"
	 dim = 3
	 break
   if (dim == 2):
      #
      # read 2D DXF
      #
      line = 0
      direction = "CCW"
      while line < nlines:
         if (find(str[line],"$ANGDIR") == 0):
	    print "angdir"
	    while 1:
	       if (strip(str[line]) == "70"):
	          line += 1
	          if (strip(str[line]) == "1"):
		     direction = "CW"
	          elif (strip(str[line]) != "0"):
		     print "$ANGDIR error"
		  break
	       else:
	          line += 1
	    line += 1
         elif (find(str[line],"POLYLINE") == 0):
            line += 1
            segment += 1
   	    boundary.append([])
	    xold = yold = []
	    while 1:
               if (find(str[line],"VERTEX") != -1):
                  line += 1
	          while 1:
 	  	     if (strip(str[line]) == "10"):
                        line += 1
                        x = float(str[line])
                     elif (strip(str[line]) == "20"):
                        line += 1
                        y = float(str[line])
    	                if ((x != xold) | (y != yold)):
   	                   # add to boundary if not zero-length segment
                           boundary[segment].append([float(x),float(y),[]])
	                   xold = x
	                   yold = y
		        break
		     else: # end VERTEX
		        line += 1
               elif (find(str[line],"SEQEND") != -1):
	          line += 1
		  break
	       else:
	          line += 1 # end POLYLINE
         elif (find(str[line],"ARC") == 0):
	    print "ARC"
            line += 1
            segment += 1
   	    boundary.append([])
	    while 1:
               if (strip(str[line]) == "10"):
                  line += 1
                  x0 = float(str[line])
               elif (strip(str[line]) == "20"):
                  line += 1
                  y0 = float(str[line])
               elif (strip(str[line]) == "40"):
                  line += 1
                  r = float(str[line])
               elif (strip(str[line]) == "50"):
                  line += 1
                  start = pi*float(str[line])/180.0
               elif (strip(str[line]) == "51"):
                  line += 1
                  end = pi*float(str[line])/180.0
		  if ((direction == "CW") & (end > start)):
		     start = start + 2*pi
		  elif ((direction == "CCW") & (end < start)):
		     end = end + 2*pi
		  for i in range(2*nverts):
		     angle = start + i*(end-start)/(2*nverts-1.0)
		     x = x0 + r*cos(angle)
		     y = y0 + r*sin(angle)
                     boundary[segment].append([float(x),float(y),[]])
		  break
	       else:
	          line += 1 # end ARC
         elif (find(str[line],"CIRCLE") == 0):
            line += 1
            segment += 1
   	    boundary.append([])
	    while 1:
               if (strip(str[line]) == "10"):
                  line += 1
                  x0 = float(str[line])
               elif (strip(str[line]) == "20"):
                  line += 1
                  y0 = float(str[line])
               elif (strip(str[line]) == "40"):
                  line += 1
                  r = float(str[line])
		  for i in range(2*nverts):
		     angle = i*2*pi/(2*nverts-1.0)
		     x = x0 + r*cos(angle)
		     y = y0 - r*sin(angle)
                     boundary[segment].append([float(x),float(y),[]])
		  break
	       else:
	          line += 1 # end CIRCLE
         elif (find(str[line],"LINE") == 0):
            line += 1
            segment += 1
   	    boundary.append([])
	    while 1:
               if (strip(str[line]) == "10"):
                  line += 1
                  x0 = float(str[line])
               elif (strip(str[line]) == "20"):
                  line += 1
                  y0 = float(str[line])
                  boundary[segment].append([x0,y0,[]])
               elif (strip(str[line]) == "11"):
                  line += 1
                  x1 = float(str[line])
               elif (strip(str[line]) == "21"):
                  line += 1
                  y1 = float(str[line])
                  boundary[segment].append([x1,y1,[]])
		  break
	       else:
	          line += 1 # end LINE
         else:
	    line += 1
      boundarys.append(boundary)
   else:
      #
      # read 3D DXF
      #
      vertex = 0
      line = 0
      while line < nlines:
         if (find(str[line],"VERTEX") != -1):
	    vertex = 1
         elif (strip(str[line]) == "10"):
            line += 1
            x = float(str[line])
         elif (strip(str[line]) == "20"):
            line += 1
            y = float(str[line])
         elif (strip(str[line]) == "30"):
            line += 1
            z = float(str[line])
         elif ((strip(str[line]) == "70") & (vertex == 1)):
	    line += 1
	    vertex = 0
	    if (strip(str[line]) == "192"):
	       vertices.append([x,y,z])
	    elif (strip(str[line]) == "128"):
	       face = []
	       if (strip(str[line+1]) == "71"):
	          line += 2
		  face.append(int(strip(str[line])))
	       if (strip(str[line+1]) == "72"):
	          line += 2
		  face.append(int(strip(str[line])))
	       if (strip(str[line+1]) == "73"):
	          line += 2
		  face.append(int(strip(str[line])))
	       if (strip(str[line+1]) == "74"):
	          line += 2
		  face.append(int(strip(str[line])))
	       faces.append(face)
	    else:
	       print "shouldn't happen (reading DXF)"
	       return
         line += 1

def read_image(filename):
   global vertices, faces, boundarys, noise_flag
   #
   # read z bitmap (incomplete)
   #
   noise_flag = 0
   image = Image.open(filename)
   (ncol,nrow) = image.size
   xdpi = image.info["dpi"][0]
   ydpi = image.info["dpi"][1]
   print "   image size: %dx%d dpi: %dx%d mode: %s"%(nrow,ncol,xdpi,ydpi,image.mode)
   zmin = HUGE
   zmax = -HUGE
   vertices = []
   boundarys = []
   print "   reading ..."
   im = list(image.getdata())
   for row in range(nrow):
      for col in range(ncol):
	 x = col/float(xdpi)
	 y = row/float(ydpi)
	 if (image.mode == "L"):
            z = float(im[col+(nrow-row-1)*ncol])
	 elif (image.mode == "RGB"):
            (r,g,b) = im[col+(nrow-row-1)*ncol]
            z = sqrt(r*r + g*g + b*b)
         if (z < zmin): zmin = z
         if (z > zmax): zmax = z
	 vertices.append([x,y,z])
   print "   scaling %d-%d ..."%(zmin,zmax)
   for vertex in range(len(vertices)):
#     vertices[vertex] = [vertices[vertex][X], vertices[vertex][Y], \
#	(vertices[vertex][Z]-zmin)/(zmax-zmin)]
     vertices[vertex] = [vertices[vertex][X], vertices[vertex][Y], \
	(zmax-vertices[vertex][Z])/(zmax-zmin)]
   print "   storing ..."
   faces = []
   for row in range(nrow-1):
      for col in range(ncol-1):
         face = []
	 face.append(1+ncol*row + col)
	 face.append(1+ncol*row + col+1)
	 face.append(1+ncol*(row+1) + col+1)
	 face.append(1+ncol*(row+1) + col)
	 faces.append(face)

def read_SVG(filename):
   global boundarys
   #
   # SVG parser
   #
   def path_get_next_number(ptr):
      notdigits = ['M','C','L','z','Z','"']
      separators = [' ',',']
      string = ""
      while 1:
         char = str[ptr]
         if (char in separators):
            ptr += 1
         else:
   	    break
      while 1:
         char = str[ptr]
	 if (char in digits):
	    string = string+char
            ptr += 1
 	 else:
	    break
      return (float(string),ptr)
   file = open(filename,'r')
   str = file.read()
   file.close()
   boundary = []
   boundarys = [[]]
   z = []
   segment = -1
   layer = 0
   grayscale = FALSE
   pointer = 0
   while 1:
      #
      # check for use of grayscale in file
      #
      pointer = find(str,'stroke:rgb(',pointer)
      if (pointer == -1):
         break
      start = pointer + 11
      end = find(str,',',start+1)
      red = float(str[start:end])
      start = end + 1
      end = find(str,',',start+1)
      green = float(str[start:end])
      start = end+1
      end = find(str,')',start+1)
      blue = float(str[start:end])
      intensity = -(red + green + blue)/3.0
      if (intensity != 0):
         grayscale = TRUE
	 break
      pointer += 4
   pointer = 0
   while 1:
      #
      # loop over elements
      #
      pointer = find(str,"<",pointer)
      if (pointer == -1):
         break
      pointer += 1
      if (str[pointer:(pointer+3)] == "svg"):
         #
	 # svg
	 #
         if (find(str,'width="',pointer) == -1):
	    width = []
	 else:
            start = find(str,'width="',pointer)
	    if (find(str,'mm"',start+7) != -1):
 	       end = find(str,'mm',start+7)
  	       width = float(str[start+7:end])
  	       print "   width: %.3fmm"%width
	       width = width/25.4
	    elif (find(str,'in"',start+7) != -1):
 	       end = find(str,'in',start+7)
  	       width = float(str[start+7:end])
  	       print "   width: %.3fin"%width
	    elif (find(str,'pt"',start+7) != -1):
 	       end = find(str,'pt',start+7)
  	       width = float(str[start+7:end])
  	       print "   width: %.3fin"%width
	       width = width/72.0
	    elif (find(str,'"',start+7) != -1):
 	       end = find(str,'"',start+7)
  	       width = float(str[start+7:end])
  	       print "   width: %.3f"%width
         if (find(str,'height="',pointer) == -1):
	    height = []
	 else:
            start = find(str,'height="',pointer)
	    if (find(str,'mm"',start+8) != -1):
 	       end = find(str,'mm',start+8)
  	       height = float(str[start+8:end])
  	       print "   height: %.3fmm"%height
	       height = height/25.4
	    elif (find(str,'in"',start+8) != -1):
 	       end = find(str,'in',start+8)
  	       height = float(str[start+8:end])
  	       print "   height: %.3fin"%height
	    elif (find(str,'pt"',start+8) != -1):
 	       end = find(str,'pt',start+8)
  	       height = float(str[start+8:end])
  	       print "   height: %.3fin"%height
	       height = height/72.0
	    elif (find(str,'"',start+8) != -1):
 	       end = find(str,'"',start+8)
  	       height = float(str[start+8:end])
  	       print "   height: %.3f"%height
         if (find(str,'viewBox="') != -1):
            s0 = find(str,'viewBox="')
  	    s1 = find(str,' ',s0+1)
	    s2 = find(str,' ',s1+1)
	    s3 = find(str,' ',s2+1)
	    s4 = find(str,'"',s3+1)
	    view_xmin = float(str[s0+9:s1])
	    view_ymin = float(str[s1+1:s2])
	    view_width = float(str[s2+1:s3])
	    view_height = float(str[s3+1:s4])
	    if (width == []):
	       width = view_width/2540
	    if (height == []):
	       height = view_height/2540
	    print "   view: %d %d %d %d"%(view_xmin,view_ymin,view_width,view_height)
	 else:
	    view_xmin = 0
	    view_ymin = 0
	    view_width = width
	    view_height = height
      elif (str[pointer:(pointer+7)] == 'g style'):
         #
	 # g
	 #
	 if (find(str,'stroke:none',pointer) != -1):
	    #
	    # skip the element if it's not stroked
	    #
	    if (find(str,'stroke:none',pointer) < find(str,'</g>',pointer)):
	       pointer = find(str,'</g>',pointer)
	       continue
	 if ((find(str,'rgb(',pointer) != -1) & (grayscale == TRUE)):
	    start = find(str,'rgb(',pointer) + 4
	    end = find(str,',',start+1)
	    red = float(str[start:end])
	    start = end + 1
	    end = find(str,',',start+1)
	    green = float(str[start:end])
	    start = end+1
	    end = find(str,')',start+1)
	    blue = float(str[start:end])
	    intensity = -(red + green + blue)/3.0
	    if (z != []):
	       layer += 1
	       boundarys.append([])
	       segment = -1
	    z = intensity
      elif (str[pointer:(pointer+8)] == 'polyline'):
         #
	 # polyline
	 #
         start = 8+find(str,'points="',pointer)
         end = find(str,'"',start+1)
	 segment += 1
	 boundarys[layer].append([])
	 while 1:
            comma = find(str,',',start)
            space = find(str,' ',start)
	    if (space > end):
	       space = end
  	    x = float(str[start:comma])
	    y = float(str[comma+1:space])
	    x = width*(x - view_xmin)/view_width
	    y = height*(view_ymin-y)/view_height
	    if (grayscale == FALSE):
	       boundarys[layer][segment].append([x,y,[]])
	    else:
	       boundarys[layer][segment].append([x,y,[],z])
	    start = space+1
	    if (space == end):
	        break
      elif (str[pointer:(pointer+7)] == 'polygon'):
         #
	 # polygon
	 #
         start = 8+find(str,'points="',pointer)
         end = find(str,'"',start+1)
	 segment += 1
	 boundarys[layer].append([])
	 while 1:
            comma = find(str,',',start)
            space = find(str,' ',start)
	    if ((space > end) | (space == -1)):
	       space = end
  	    x = float(str[start:comma])
	    y = float(str[comma+1:space])
	    x = width*(x - view_xmin)/view_width
	    y = height*(view_ymin-y)/view_height
	    if (grayscale == FALSE):
	       boundarys[layer][segment].append([x,y,[]])
	    else:
	       boundarys[layer][segment].append([x,y,[],z])
	    start = space+1
	    if (space == end):
	        break
      elif (str[pointer:(pointer+4)] == 'path'):
         #
	 # path
	 #
         digits = ['0','1','2','3','4','5','6','7','8','9','.','-']
	 segment += 1
	 boundarys[layer].append([])
	 while 1:
            ptr = find(str,'d="',pointer)
	    if (str[ptr-1] == 'i'):
	       pointer = ptr+1
	       continue
	    else:
	       ptr = ptr + 3
	       break
	 while 1:
	    char = str[ptr]
	    if (char == 'M'):
	       ptr += 1
	       (x0,ptr) = path_get_next_number(ptr)
	       (y0,ptr) = path_get_next_number(ptr)
	       x0 = width*(x0 - view_xmin)/view_width
	       y0 = height*(view_ymin-y0)/view_height
   	       if (grayscale == FALSE):
	          boundarys[layer][segment].append([x0,y0,[]])
	       else:
	          boundarys[layer][segment].append([x0,y0,[],z])
	    elif (char == 'L'):
	       ptr += 1
	       (x1,ptr) = path_get_next_number(ptr)
	       (y1,ptr) = path_get_next_number(ptr)
	       x1 = width*(x1 - view_xmin)/view_width
	       y1 = height*(view_ymin-y1)/view_height
  	       if (grayscale == FALSE):
	          boundarys[layer][segment].append([x1,y1,[]])
	       else:
	          boundarys[layer][segment].append([x1,y1,[],z])
	    elif (char == 'C'):
	       ptr += 1
	       (x1,ptr) = path_get_next_number(ptr)
	       (y1,ptr) = path_get_next_number(ptr)
	       x1 = width*(x1 - view_xmin)/view_width
	       y1 = height*(view_ymin-y1)/view_height
	       (x2,ptr) = path_get_next_number(ptr)
	       (y2,ptr) = path_get_next_number(ptr)
	       x2 = width*(x2 - view_xmin)/view_width
	       y2 = height*(view_ymin-y2)/view_height
	       (x3,ptr) = path_get_next_number(ptr)
	       (y3,ptr) = path_get_next_number(ptr)
	       x3 = width*(x3 - view_xmin)/view_width
	       y3 = height*(view_ymin-y3)/view_height
	       for i in range(nverts):
	          u = i/(nverts-1.0)
	          x = ((1-u)**3 * x0) + (3*u*(1-u)**2 * x1) \
		     + (3*u**2*(1-u) * x2) + (u**3 * x3)
	          y = ((1-u)**3 * y0) + (3*u*(1-u)**2 * y1) \
		     + (3*u**2*(1-u) * y2) + (u**3 * y3)
	          if (grayscale == FALSE):
	             boundarys[layer][segment].append([x,y,[]])
	          else:
	             boundarys[layer][segment].append([x,y,[],z])
	       x0 = x3
	       y0 = y3
	    elif (char in digits):
	       (x1,ptr) = path_get_next_number(ptr)
	       (y1,ptr) = path_get_next_number(ptr)
	       x1 = width*(x1 - view_xmin)/view_width
	       y1 = height*(view_ymin-y1)/view_height
	       if (grayscale == FALSE):
	          boundarys[layer][segment].append([x1,y1,[]])
	       else:
	          boundarys[layer][segment].append([x1,y1,[],z])
            elif (char == '"'):
	       break
	    else:
 	       ptr += 1
      #(1-u)^3
      #3u(1-u)^2
      #3u^2(1-u)
      #u^3
      elif (str[pointer:(pointer+4)] == 'rect'):
         """
         #
	 # rectangle
	 #
         start = 7+find(str,'width="',pointer)
         end = find(str,'"',start+1)
         rect_width = float(str[start:end])
         start = 8+find(str,'height="',end)
         end = find(str,'"',start+1)
         rect_height = float(str[start:end])
	 sys.exit()
	 segment += 1
	 boundarys[layer].append([])
         x = width*(x - view_xmin)/view_width
         y = height*(view_ymin-y)/view_height
         if (grayscale == FALSE):
            boundarys[layer][segment].append([x,y,[]])
         else:
            boundarys[layer][segment].append([x,y,[],z])
         start = end+1
    if (space == end):
        break
	"""
         print "SVG rect not yet implemented"
      elif (str[pointer:(pointer+4)] == 'line'):
         print "SVG line not yet implemented"
      elif (str[pointer:(pointer+6)] == 'circle'):
         print "SVG circle not yet implemented"
      elif (str[pointer:(pointer+7)] == 'polygon'):
         print "SVG polygon not yet implemented"
      elif (str[pointer:(pointer+7)] == 'ellipse'):
         print "SVG ellipse not yet implemented"

def read(event):
   global vertices, faces, boundarys, toolpaths, contours, slices,\
      xmin, xmax, ymin, ymax, zmin, zmax, noise_flag
   #
   # read file
   #
   faces = []
   contours = [[]]
   boundarys = [[]]
   toolpaths = [[]]
   slices = [[]]
   filename = infile.get()
   if ((find(filename,".cmp") != -1) | (find(filename,".CMP")!= -1) \
      | (find(filename,".sol")!= -1) | (find(filename,".SOL") != -1) \
      | (find(filename,".via")!= -1) | (find(filename,".VIA")!= -1)
      | (find(filename,".mill")!= -1) | (find(filename,".MILL")!= -1)):
      print "reading Gerber file",filename
      read_Gerber(filename)
   elif ((find(filename,".drl") != -1) | (find(filename,".DRL") != -1) | \
      (find(filename,".drd") != -1) | (find(filename,".DRD") != -1)):
      print "reading Excellon file",filename
      read_Excellon(filename)
   elif ((find(filename,".dxf") != -1) | (find(filename,".DXF") != -1)):
      print "reading DXF file",filename
      read_DXF(filename)
   elif (find(filename,".stl") != -1):
      print "reading STL file",filename
      read_STL(filename)
   elif (find(filename,".jpg") != -1):
      print "reading image file",filename
      read_image(filename)
   elif (find(filename,".svg") != -1):
      print "reading SVG file",filename
      read_SVG(filename)
   else:
      print "unsupported file type"
      return
   xmin = HUGE
   xmax = -HUGE
   ymin = HUGE
   ymax = -HUGE
   zmin = HUGE
   zmax = -HUGE
   if (len(boundarys) == 1):
      #
      # 2D file
      #
      boundary = boundarys[0]
      sum = 0
      for segment in range(len(boundary)):
         sum += len(boundary[segment])
         for vertex in range(len(boundary[segment])):
            x = boundary[segment][vertex][X]
            y = boundary[segment][vertex][Y]
            if (x < xmin): xmin = x
            if (x > xmax): xmax = x
            if (y < ymin): ymin = y
            if (y > ymax): ymax = y
      print "   found",len(boundary),"polygons,",sum,"vertices"
      print "   xmin: %0.3g "%xmin,"xmax: %0.3g "%xmax,"dx: %0.3g "%(xmax-xmin)
      print "   ymin: %0.3g "%ymin,"ymax: %0.3g "%ymax,"dy: %0.3g "%(ymax-ymin)
      if (noise_flag == 1):
         if ((xmax-xmin) < (ymax-ymin)):
            delta = (xmax-xmin)*NOISE
         else:
            delta = (ymax-ymin)*NOISE
         for segment in range(len(boundary)):
            for vertex in range(len(boundary[segment])):
               boundary[segment][vertex][X] += gauss(0,delta)
               boundary[segment][vertex][Y] += gauss(0,delta)
         print "   added %.3g perturbation"%delta
      boundarys[0] = boundary
   elif (len(boundarys) > 1):
      #
      # 3D layers
      #
      for layer in range(len(boundarys)):
         boundary = boundarys[layer]
         sum = 0
         for segment in range(len(boundary)):
            sum += len(boundary[segment])
            for vertex in range(len(boundary[segment])):
               x = boundary[segment][vertex][X3]
               y = boundary[segment][vertex][Y3]
               z = boundary[segment][vertex][Z3]
               if (x < xmin): xmin = x
               if (x > xmax): xmax = x
               if (y < ymin): ymin = y
               if (y > ymax): ymax = y
               if (z < zmin): zmin = z
               if (z > zmax): zmax = z
         print "   layer",layer,"found",len(boundary),"polygon(s),",sum,"vertices"
         if (noise_flag == 1):
            if ((xmax-xmin) < (ymax-ymin)):
               delta = (xmax-xmin)*NOISE
            else:
               delta = (ymax-ymin)*NOISE
            for segment in range(len(boundary)):
               for vertex in range(len(boundary[segment])):
                  boundary[segment][vertex][X3] += gauss(0,delta)
                  boundary[segment][vertex][Y3] += gauss(0,delta)
                  boundary[segment][vertex][Z3] += gauss(0,delta)
         boundarys[layer] = boundary
      print "   xmin: %0.3g "%xmin,"xmax: %0.3g "%xmax,"dx: %0.3g "%(xmax-xmin)
      print "   ymin: %0.3g "%ymin,"ymax: %0.3g "%ymax,"dy: %0.3g "%(ymax-ymin)
      print "   zmin: %0.3g "%zmin,"zmax: %0.3g "%zmax,"dy: %0.3g "%(zmax-zmin)
      print "   added %.3g perturbation"%delta
   elif (faces != []):
      #
      # 3D faces
      #
      for vertex in range(len(vertices)):
         x = vertices[vertex][X]
         y = vertices[vertex][Y]
         z = vertices[vertex][Z]
         if (x < xmin): xmin = x
         if (x > xmax): xmax = x
         if (y < ymin): ymin = y
         if (y > ymax): ymax = y
         if (z < zmin): zmin = z
         if (z > zmax): zmax = z
      print "   found",len(vertices),"vertices,",len(faces),"faces"
      print "   xmin: %0.3g "%xmin,"xmax: %0.3g "%xmax,"dx: %0.3g "%(xmax-xmin)
      print "   ymin: %0.3g "%ymin,"ymax: %0.3g "%ymax,"dy: %0.3g "%(ymax-ymin)
      print "   zmin: %0.3g "%zmin,"zmax: %0.3g "%zmax,"dz: %0.3g "%(zmax-zmin)
      if (noise_flag == 1):
         delta = (zmax-zmin)*NOISE
         for vertex in range(len(vertices)):
            vertices[vertex][X] += gauss(0,delta)
            vertices[vertex][Y] += gauss(0,delta)
            vertices[vertex][Z] += gauss(0,delta)
         print "   added %.3g perturbation"%delta
   else:
      print "shouldn't happen in read"
   camselect(event)
#   plot_delete(event)

def autoscale(event):
   global xmax, xmin, ymax, ymin, zmax, zmin, fixed_size
   #
   # fit window to object
   #
   xyscale = float(sxyscale.get())
   zscale = float(szscale.get())
   sxmin.set("0")
   symin.set("0")
   szmax.set("0")
   if ((ymax-ymin) > (xmax-xmin)):
      sxysize.set(str(xyscale*(ymax-ymin)))
   else:
      sxysize.set(str(xyscale*(xmax-xmin)))
   szsize.set(str(zscale*(zmax-zmin)))
   sztop.set(szmax.get())
   szbot.set(str(float(szmax.get())-zscale*(zmax-zmin)))
   sthickness.set(str(zscale*(zmax-zmin)))
   fixed_size = True
   plot_delete(event)

def fixedscale(event):
   global xmax, xmin, ymax, ymin, zmax, zmin, fixed_size
   #
   # show object at original scale and location
   #
   fixed_size = False
   camselect(event)
   xyscale = float(sxyscale.get())
   sxmin.set(str(xmin*xyscale))
   symin.set(str(ymin*xyscale))
   plot_delete(event)

def stroke(x0,y0,x1,y1,width):
   #
   # stroke segment with width
   #
   #print "stroke:",x0,y0,x1,y1,width
   dx = x1 - x0
   dy = y1 - y0
   d = sqrt(dx*dx + dy*dy)
   dxpar = dx / d
   dypar = dy / d
   dxperp = dypar
   dyperp = -dxpar
   dx = -dxperp * width/2.0
   dy = -dyperp * width/2.0
   angle = pi/(nverts/2-1.0)
   c = cos(angle)
   s = sin(angle)
   newpath = []
   for i in range(nverts/2):
      newpath.append([x0+dx,y0+dy,0])
      [dx,dy] = [c*dx-s*dy, s*dx+c*dy]
   dx = dxperp * width/2.0
   dy = dyperp * width/2.0
   for i in range(nverts/2):
      newpath.append([x1+dx,y1+dy,0])
      [dx,dy] = [c*dx-s*dy, s*dx+c*dy]
   x0 = newpath[0][X]
   y0 = newpath[0][Y]
   newpath.append([x0,y0,0])
   return newpath

def plot(event):
   global vertices, faces, boundarys, toolpaths, \
      xmin, xmax, ymin, ymax, zmin, zmax
   #
   # scale and plot object and toolpath
   #
   print "plotting"
   xysize = float(sxysize.get())
   zsize = float(szsize.get())
   xyscale = float(sxyscale.get())
   zscale = float(szscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   zoff = float(szmax.get()) - zmax*zscale
   sdxy.set("  dx:%6.3f  dy:%6.3f"%((xmax-xmin)*xyscale,(ymax-ymin)*xyscale))
   sdz.set("  dz:%6.3f"%((zmax-zmin)*zscale))
   vert = ivert.get()
   if (len(boundarys) == 1):
      #
      # 2D plot
      #
      c.delete("plot_boundary")
      c.delete("plot_path")
      #
      # set scrollbars
      #
      xscrollmin = (xmin*xyscale + xoff)*WINDOW/xysize
      if (xscrollmin > 0): xscrollmin = 0
      xscrollmax = (xmax*xyscale + xoff)*WINDOW/xysize
      if (xscrollmax < WINDOW): xscrollmax = WINDOW
      yscrollmin = WINDOW - (ymax*xyscale + yoff)*WINDOW/xysize
      if (yscrollmin > 0): yscrollmin = 0
      yscrollmax = WINDOW - (ymin*xyscale + yoff)*WINDOW/xysize
      if (yscrollmax < WINDOW): yscrollmax = WINDOW
      c.configure(scrollregion=(xscrollmin,yscrollmin,xscrollmax,yscrollmax))
      if (xscrollmin == 0) & (xscrollmax == WINDOW):
         xscrollbar.grid_forget()
      else:
         xscrollbar.grid(row=1, column=0, sticky=E+W)
      if (yscrollmin == 0) & (yscrollmax == WINDOW):
         yscrollbar.grid_forget()
      else:
         yscrollbar.grid(row=0, column=1, sticky=N+S)
      #
      # mark origin
      #
      c.create_line([(-WINDOW/20,WINDOW-1),(WINDOW/20,WINDOW-1)],fill="blue")
      c.create_line([(0,WINDOW+WINDOW/20),(0,WINDOW-WINDOW/20)],fill="blue")
      #
      # plot boundary segments
      #
      for seg in range(len(boundarys[0])):
         path_plot = []
         for vertex in range(len(boundarys[0][seg])):
            xplot = int((boundarys[0][seg][vertex][X]*xyscale + xoff)*WINDOW/xysize)
            path_plot.append(xplot)
            yplot = (WINDOW-1) - int((boundarys[0][seg][vertex][Y]*xyscale + yoff)*WINDOW/xysize)
            path_plot.append(yplot)
	    if (vert == 1):
	       c.create_text(xplot,yplot,text=str(seg)+':'+str(vertex),tag="plot_boundary")
         c.create_line(path_plot,tag="plot_boundary")
      c.delete("plot_path")
      #
      # plot toolpath segments
      #
      for seg in range(len(toolpaths[0])):
         path_plot = []
         for vertex in range (len(toolpaths[0][seg])):
            xplot = int((toolpaths[0][seg][vertex][X]*xyscale + xoff)*WINDOW/xysize)
            path_plot.append(xplot)
            yplot = (WINDOW-1) - int((toolpaths[0][seg][vertex][Y]*xyscale + yoff)*WINDOW/xysize)
            path_plot.append(yplot)
            if (vert == 1):
               c.create_text(xplot,yplot,text=str(seg)+':'+str(vertex),tag="plot_path")
         c.create_line(path_plot,tag="plot_path",fill="red")
   else:
      #
      # 3D plot
      #
      c.delete("plot_boundary")
      c.delete("plot_path")
      #
      # remove 2D scrollbars
      #
      xscrollbar.grid_forget()
      yscrollbar.grid_forget()
      #
      # draw 3D views
      #
      c.create_line([[WINDOW/2,0],[WINDOW/2,WINDOW]],tag="plot_boundary",fill="blue")
      c.create_line([[0,WINDOW/2],[WINDOW,WINDOW/2]],tag="plot_boundary",fill="blue")
      c.create_text(WINDOW/4,WINDOW/30,text="perspective",font=("sans-serif",12),fill="#c00000")
      c.create_text(WINDOW/2+WINDOW/4,WINDOW/30,text="front",font=("sans-serif",12),fill="#c00000")
      c.create_text(WINDOW/4,WINDOW/2+WINDOW/30,text="side",font=("sans-serif",12),fill="#c00000")
      c.create_text(WINDOW/2+WINDOW/4,WINDOW/2+WINDOW/30,text="top",font=("sans-serif",12),fill="#c00000")
      if (boundarys == []):
         for face in range(len(faces)):
            xy_plot = []
            xz_plot = []
            yz_plot = []
	    xyz_plot = []
            for vertex in range(len(faces[face])):
 	       x = vertices[faces[face][vertex]-1][X]
	       y = vertices[faces[face][vertex]-1][Y]
	       z = vertices[faces[face][vertex]-1][Z]
               xplot = WINDOW/2 + int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = WINDOW - int((y*xyscale + yoff)*WINDOW*0.5/xysize)
               xy_plot.append(xplot)
               xy_plot.append(yplot)
               xplot = WINDOW/2 + int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = -int((z*zscale + zoff)*WINDOW*0.5/zsize)
               xz_plot.append(xplot)
               xz_plot.append(yplot)
               xplot = -int((z*zscale + zoff)*WINDOW*0.5/zsize)
               yplot = WINDOW - int((y*xyscale + yoff)*WINDOW*0.5/xysize)
               yz_plot.append(xplot)
               yz_plot.append(yplot)
	       xplot = int((x*xyscale+xoff)*WINDOW*0.5/xysize)
               yplot = WINDOW/2 - int((y*xyscale + yoff)*WINDOW*0.5/xysize) - \
	          int((z*zscale + zoff)*WINDOW*0.5/(10*zsize))
               xyz_plot.append(xplot)
               xyz_plot.append(yplot)
            c.create_line(xy_plot,tag="plot_boundary")
            c.create_line(xz_plot,tag="plot_boundary")
            c.create_line(yz_plot,tag="plot_boundary")
            c.create_line(xyz_plot,tag="plot_boundary")
      for layer in range(len(boundarys)):
         for seg in range(len(boundarys[layer])):
            xy_plot = []
            xz_plot = []
            yz_plot = []
	    xyz_plot = []
	    for vertex in range(len(boundarys[layer][seg])):
	       x = boundarys[layer][seg][vertex][X3]
	       y = boundarys[layer][seg][vertex][Y3]
	       z = boundarys[layer][seg][vertex][Z3]
               xplot = WINDOW/2 + int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = WINDOW - int((y*xyscale + yoff)*WINDOW*0.5/xysize)
               xy_plot.append(xplot)
               xy_plot.append(yplot)
               xplot = WINDOW/2 + int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = -int((z*zscale + zoff)*WINDOW*0.5/zsize)
               xz_plot.append(xplot)
               xz_plot.append(yplot)
               xplot = -int((z*zscale + zoff)*WINDOW*0.5/zsize)
               yplot = WINDOW - int((y*xyscale + yoff)*WINDOW*0.5/xysize)
               yz_plot.append(xplot)
               yz_plot.append(yplot)
               xplot = int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = WINDOW/2 - int((y*xyscale + yoff)*WINDOW*0.5/xysize) - \
	          int((z*zscale + zoff)*WINDOW*0.5/(10*zsize))
               xyz_plot.append(xplot)
               xyz_plot.append(yplot)
            c.create_line(xy_plot,tag="plot_boundary")
            c.create_line(xz_plot,tag="plot_boundary")
            c.create_line(yz_plot,tag="plot_boundary")
            c.create_line(xyz_plot,tag="plot_boundary")
      for layer in range(len(toolpaths)):
         for seg in range(len(toolpaths[layer])):
            xy_plot = []
            xz_plot = []
            yz_plot = []
	    xyz_plot = []
	    for vertex in range(len(toolpaths[layer][seg])):
	       x = toolpaths[layer][seg][vertex][X3]
	       y = toolpaths[layer][seg][vertex][Y3]
	       z = toolpaths[layer][seg][vertex][Z3]
               xplot = WINDOW/2 + int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = WINDOW - int((y*xyscale + yoff)*WINDOW*0.5/xysize)
               xy_plot.append(xplot)
               xy_plot.append(yplot)
               xplot = WINDOW/2 + int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = -int((z*zscale + zoff)*WINDOW*0.5/zsize)
               xz_plot.append(xplot)
               xz_plot.append(yplot)
               xplot = -int((z*zscale + zoff)*WINDOW*0.5/zsize)
               yplot = WINDOW - int((y*xyscale + yoff)*WINDOW*0.5/xysize)
               yz_plot.append(xplot)
               yz_plot.append(yplot)
               xplot = int((x*xyscale + xoff)*WINDOW*0.5/xysize)
               yplot = WINDOW/2 - int((y*xyscale + yoff)*WINDOW*0.5/xysize) - \
	          int((z*zscale + zoff)*WINDOW*0.5/(10*zsize))
               xyz_plot.append(xplot)
               xyz_plot.append(yplot)
            c.create_line(xy_plot,tag="plot_path",fill="red")
            c.create_line(xz_plot,tag="plot_path",fill="red")
            c.create_line(yz_plot,tag="plot_path",fill="red")
            c.create_line(xyz_plot,tag="plot_path",fill="red")

def plot_delete(event):
   global boundarys, toolpaths, contours
   #
   # scale and plot boundary, delete toolpath
   #
   for layer in range(len(toolpaths)):
      toolpaths[layer] = []
      contours[layer] = []
#   print "deleted toolpath"
   plot(event)

def intersect(path,seg0,vert0,sega,verta):
   #
   # test and return edge intersection
   #
   if ((seg0 == sega) & (vert0 == 0) & (verta == (len(path[sega])-2))):
      #print "   return (0-end)"
      return [[],[]]
   x0 = path[seg0][vert0][X]
   y0 = path[seg0][vert0][Y]
   x1 = path[seg0][vert0+1][X]
   y1 = path[seg0][vert0+1][Y]
   dx01 = x1 - x0
   dy01 = y1 - y0
   d01 = sqrt(dx01*dx01 + dy01*dy01)
   if (d01 == 0):
      #
      # zero-length segment, return no intersection
      #
      #print "zero-length segment"
      return [[],[]]
   dxpar01 = dx01 / d01
   dypar01 = dy01 / d01
   dxperp01 = dypar01
   dyperp01 = -dxpar01
   xa = path[sega][verta][X]
   ya = path[sega][verta][Y]
   xb = path[sega][verta+1][X]
   yb = path[sega][verta+1][Y]
   dx0a = xa - x0
   dy0a = ya - y0
   dpar0a = dx0a*dxpar01 + dy0a*dypar01
   dperp0a = dx0a*dxperp01 + dy0a*dyperp01
   dx0b = xb - x0
   dy0b = yb - y0
   dpar0b = dx0b*dxpar01 + dy0b*dypar01
   dperp0b = dx0b*dxperp01 + dy0b*dyperp01
   #if (dperp0a*dperp0b > EPS):
   if (((dperp0a > EPS) & (dperp0b > EPS)) | \
      ((dperp0a < -EPS) & (dperp0b < -EPS))):
      #
      # vertices on same side, return no intersection
      #
      #print " same side"
      return [[],[]]
   elif ((abs(dperp0a) < EPS) & (abs(dperp0b) < EPS)):
      #
      # edges colinear, return no intersection
      #
      #d0a = (xa-x0)*dxpar01 + (ya-y0)*dypar01
      #d0b = (xb-x0)*dxpar01 + (yb-y0)*dypar01
      #print " colinear"
      return [[],[]]
   #
   # calculation distance to intersection
   #
   d = (dpar0a*abs(dperp0b)+dpar0b*abs(dperp0a))/(abs(dperp0a)+abs(dperp0b))
   if ((d < -EPS) | (d > (d01+EPS))):
      #
      # intersection outside segment, return no intersection
      #
      #print "   found intersection outside segment"
      return [[],[]]
   else:
      #
      # intersection in segment, return intersection
      #
      #print "   found intersection in segment s0 v0 sa va",seg0,vert0,sega,verta
      xloc = x0 + dxpar01*d
      yloc = y0 + dypar01*d
      return [xloc,yloc]

def union(i,path,intersections,sign):
   #
   # return edge to exit intersection i for a union
   #
   #print "union: intersection",i,"in",intersections
   seg0 = intersections[i][0][SEG]
   #print "seg0",seg0
   vert0 = intersections[i][0][VERT]
   x0 = path[seg0][vert0][X]
   y0 = path[seg0][vert0][Y]
   if (vert0 < (len(path[seg0])-1)):
      vert1 = vert0 + 1
   else:
      vert1 = 0
   x1 = path[seg0][vert1][X]
   y1 = path[seg0][vert1][Y]
   dx01 = x1-x0
   dy01 = y1-y0
   sega = intersections[i][A][SEG]
   verta = intersections[i][A][VERT]
   xa = path[sega][verta][X]
   ya = path[sega][verta][Y]
   if (verta < (len(path[sega])-1)):
      vertb = verta + 1
   else:
      vertb = 0
   xb = path[sega][vertb][X]
   yb = path[sega][vertb][Y]
   dxab = xb-xa
   dyab = yb-ya
   dot = dxab*dy01 - dyab*dx01
   #print "   dot",dot
   if (abs(dot) <= EPS):
      print "   colinear"
      seg = []
      vert= []
   elif (dot > EPS):
      seg = intersections[i][(1-sign)/2][SEG]
      vert = intersections[i][(1-sign)/2][VERT]
   else:
      seg = intersections[i][(1+sign)/2][SEG]
      vert = intersections[i][(1+sign)/2][VERT]
   return [seg,vert]

def insert(path,x,y,seg,vert,intersection):
   #
   # insert a vertex at x,y in seg,vert, if needed
   #
   d0 = (path[seg][vert][X]-x)**2 + (path[seg][vert][Y]-y)**2
   d1 = (path[seg][vert+1][X]-x)**2 + (path[seg][vert+1][Y]-y)**2
   #print "check insert seg",seg,"vert",vert,"intersection",intersection
   if ((d0 > EPS) & (d1 > EPS)):
      #print "   added intersection vertex",vert+1
      path[seg].insert((vert+1),[x,y,intersection])
      return 1
   elif (d0 < EPS):
      if (path[seg][vert][INTERSECT] == []):
         path[seg][vert][INTERSECT] = intersection
         #print "   added d0",vert
      return 0
   elif (d1 < EPS):
      if (path[seg][vert+1][INTERSECT] == []):
         path[seg][vert+1][INTERSECT] = intersection
         #print "   added d1",vert+1
      return 0
   else:
      #print "   shouldn't happen: d0",d0,"d1",d1
      return 0

def add_intersections(path):
   #
   # add vertices at path intersections
   #
   events = []
   active = []
   #
   # lexicographic sort segments
   #
   for seg in range(len(path)):
      nverts = len(path[seg])
      for vert in range(nverts-1):
         x0 = path[seg][vert][X]
         y0 = path[seg][vert][Y]
         x1 = path[seg][vert+1][X]
         y1 = path[seg][vert+1][Y]
	 if (x1 < x0):
	    [x0, x1] = [x1, x0]
	    [y0, y1] = [y1, y0]
	 if ((x1 == x0) & (y1 < y0)):
	    [y0, y1] = [y1, y0]
	 events.append([x0,y0,START,seg,vert])
	 events.append([x1,y1,END,seg,vert])
   events.sort()
   #
   # find intersections with a sweep line
   #
   intersection = 0
   verts = []
   for event in range(len(events)):
#      status.set("   edge "+str(event)+"/"+str(len(events)-1)+"  ")
#      outframe.update()
      #
      # loop over start/end points
      #
      type = events[event][INDEX]
      seg0 = events[event][EVENT_SEG]
      vert0 = events[event][EVENT_VERT]
      n0 = len(path[seg0])
      if (events[event][INDEX] == START):
         #
	 # loop over active points
	 #
	 for point in range(len(active)):
	    sega = active[point][SEG]
	    verta = active[point][VERT]
	    if ((sega == seg0) & \
	       ((abs(vert0-verta) == 1) | (abs(vert0-verta) == (n0-2)))):
	       #print seg0,vert0,verta,n0
	       continue
	    [xloc,yloc] = intersect(path,seg0,vert0,sega,verta)
	    if (xloc != []):
	       #
	       # found intersection, save it
	       #
	       d0 = (path[seg0][vert0][X]-xloc)**2 + (path[seg0][vert0][Y]-yloc)**2
	       verts.append([seg0,vert0,d0,xloc,yloc,intersection])
	       da = (path[sega][verta][X]-xloc)**2 + (path[sega][verta][Y]-yloc)**2
	       verts.append([sega,verta,da,xloc,yloc,intersection])
	       intersection += 1
         active.append([seg0,vert0])
      else:
         active.remove([seg0,vert0])
   print "   found",intersection,"intersections"
   #
   # add vertices at path intersections
   #
   verts.sort()
   verts.reverse()
   for vertex in range(len(verts)):
      seg = verts[vertex][SEG]
      vert = verts[vertex][VERT]
      intersection = verts[vertex][IINTERSECT]
      x = verts[vertex][XINTERSECT]
      y = verts[vertex][YINTERSECT]
      insert(path,x,y,seg,vert,intersection)
   #
   # make vertex table and segment list of intersections
   #
#   status.set(namedate)
#   outframe.update()
   nintersections = len(verts)/2
   intersections = [[] for i in range(nintersections)]
   for seg in range(len(path)):
      for vert in range(len(path[seg])):
         intersection = path[seg][vert][INTERSECT]
	 if (intersection != []):
	    intersections[intersection].append([seg,vert])
   seg_intersections = [[] for i in path]
   for i in range(len(intersections)):
      if (len(intersections[i]) != 2):
         print "   shouldn't happen: i",i,intersections[i]
      else:
         seg_intersections[intersections[i][0][SEG]].append(i)
         seg_intersections[intersections[i][A][SEG]].append(i)
   return [path, intersections, seg_intersections]

def offset(x0,x1,x2,y0,y1,y2,r):
   #
   # calculate offset by r for vertex 1
   #
   dx0 = x1 - x0
   dx1 = x2 - x1
   dy0 = y1 - y0
   dy1 = y2 - y1
   d0 = sqrt(dx0*dx0 + dy0*dy0)
   d1 = sqrt(dx1*dx1 + dy1*dy1)
   if ((d0 == 0) | (d1 == 0)):
      return [[],[]]
   dx0par = dx0 / d0
   dy0par = dy0 / d0
   dx0perp = dy0 / d0
   dy0perp = -dx0 / d0
   dx1perp = dy1 / d1
   dy1perp = -dx1 / d1
   #print "offset points:",x0,x1,x2,y0,y1,y2
   #print "offset normals:",dx0perp,dx1perp,dy0perp,dy1perp
   if ((abs(dx0perp*dy1perp - dx1perp*dy0perp) < EPS) | \
        (abs(dy0perp*dx1perp - dy1perp*dx0perp) < EPS)):
       dx = r * dx1perp
       dy = r * dy1perp
       #print "   offset planar:",dx,dy
   elif ((abs(dx0perp+dx1perp) < EPS) & (abs(dy0perp+dy1perp) < EPS)):
      dx = r * dx1par
      dy = r * dy1par
      #print "   offset hairpin:",dx,dy
   else:
      dx = r*(dy1perp - dy0perp) / \
           (dx0perp*dy1perp - dx1perp*dy0perp)
      dy = r*(dx1perp - dx0perp) / \
           (dy0perp*dx1perp - dy1perp*dx0perp)
      #print "   offset OK:",dx,dy
   return [dx,dy]

def displace(path,toolrad):
   #
   # displace path inwards by tool radius
   #
   print "   displacing ..."
   newpath = []
   for seg in range(len(path)):
      newpath.append([])
      if (len(path[seg]) > 2):
         for vert1 in range(len(path[seg])-1):
            if (vert1 == 0):
	       vert0 = len(path[seg]) - 2
	    else:
	       vert0 = vert1 - 1
	    vert2 = vert1 + 1
	    x0 = path[seg][vert0][X]
	    x1 = path[seg][vert1][X]
	    x2 = path[seg][vert2][X]
	    y0 = path[seg][vert0][Y]
	    y1 = path[seg][vert1][Y]
	    y2 = path[seg][vert2][Y]
	    [dx,dy] = offset(x0,x1,x2,y0,y1,y2,toolrad)
	    if (dx != []):
	       newpath[seg].append([(x1+dx),(y1+dy),[]])
         x0 = newpath[seg][0][X]
         y0 = newpath[seg][0][Y]
         newpath[seg].append([x0,y0,[]])
      elif (len(path[seg]) == 2):
         x0 = path[seg][0][X]
	 y0 = path[seg][0][Y]
	 x1 = path[seg][1][X]
	 y1 = path[seg][1][Y]
	 x2 = 2*x1 - x0
	 y2 = 2*y1 - y0
	 [dx,dy] = offset(x0,x1,x2,y0,y1,y2,toolrad)
	 if (dx != []):
	    newpath[seg].append([x0+dx,y0+dy,[]])
	    newpath[seg].append([x1+dx,y1+dy,[]])
	 else:
	    newpath[seg].append([x0,y0,[]])
	    newpath[seg].append([x1,y1,[]])
      else:
         print "  displace: shouldn't happen"
   return newpath

def prune(path,sign,event):
   #
   # prune path intersections
   #
   # first find the intersections
   #
   print "   intersecting ..."
   [path, intersections, seg_intersections] = add_intersections(path)
   #print 'path:',path
   #print 'intersections:',intersections
   #print 'seg_intersections:',seg_intersections
   #
   # then copy non-intersecting segments to new path
   #
   newpath = []
   for seg in range(len(seg_intersections)):
      #print "non-int"
      if (seg_intersections[seg] == []):
	 newpath.append(path[seg])
   #
   # finally follow and remove the intersections
   #
   print "   pruning ..."
   i = 0
   newseg = 0
   while (i < len(intersections)):
      if (intersections[i] == []):
         #
	 # skip null intersections
	 #
         i += 1
	 #print "null"
      else:
         istart = i
	 intersection = istart
	 #
	 # skip interior intersections
	 #
	 oldseg = -1
	 interior = TRUE
	 while 1:
	    #print 'testing intersection',intersection,':',intersections[intersection]
	    if (intersections[intersection] == []):
	       #seg == oldseg
	       seg = oldseg
            else:
	       [seg,vert] = union(intersection,path,intersections,sign)
               #print '  seg',seg,'vert',vert,'oldseg',oldseg
            if (seg == oldseg):
               #print "   remove interior intersection",istart
               seg0 = intersections[istart][0][SEG]
               vert0 = intersections[istart][0][VERT]
               path[seg0][vert0][INTERSECT] = -1
               seg1 = intersections[istart][1][SEG]
               vert1 = intersections[istart][1][VERT]
               path[seg1][vert1][INTERSECT] = -1
               intersections[istart] = []
               break
	    elif (seg == []):
	       seg = intersections[intersection][0][SEG]
	       vert = intersections[intersection][0][SEG]
	       oldseg = []
            else:
               oldseg = seg
            intersection = []
	    while (intersection == []):
	       if (vert < (len(path[seg])-1)):
	          vert += 1
	       else:
	          vert = 0
	       intersection = path[seg][vert][INTERSECT]
	    if (intersection == -1):
	       intersection = istart
	       break
	    elif (intersection == istart):
	       #print '   back to',istart
	       interior = FALSE
	       intersection = istart
	       break
	 #
	 # save path if valid boundary intersection
	 #
	 if (interior == FALSE):
            newseg = len(newpath)
	    newpath.append([])
	    while 1:
	       #print 'keeping intersection',intersection,':',intersections[intersection]
	       [seg,vert] = union(intersection,path,intersections,sign)
	       if (seg == []):
	          seg = intersections[intersection][0][SEG]
	          vert = intersections[intersection][0][VERT]
	       #print '  seg',seg,'vert',vert
	       intersections[intersection] = []
	       intersection = []
	       while (intersection == []):
	          if (vert < (len(path[seg])-1)):
	             x = path[seg][vert][X]
	             y = path[seg][vert][Y]
	             newpath[newseg].append([x,y,[]])
	             vert += 1
	          else:
	             vert = 0
	          intersection = path[seg][vert][INTERSECT]
	       if (intersection == istart):
	          #print '   back to',istart
	          x = path[seg][vert][X]
	          y = path[seg][vert][Y] 
	          newpath[newseg].append([x,y,[]])
	          break
         i += 1
   return newpath

def union_boundary(event):
   global boundary, intersections
   #
   # union intersecting polygons on boundary
   #
   print "union boundary ..."
   for layer in range(len(boundarys)):
      boundarys[layer] = prune(boundarys[layer],1,event)
   print "   done"
   plot(event)

def orient(path):
   sum = xsum = ysum = zsum = 0
   for segment in range(len(path)):
      for vertex in range(len(path[segment])):
         x = path[segment][vertex][X3]
         y = path[segment][vertex][Y3]
         z = path[segment][vertex][Z3]
	 xsum += x
	 ysum += y
	 zsum += z
	 sum += 1
   xmean = xsum/sum
   ymean = ysum/sum
   zmean = zsum/sum
   sum = xsum = ysum = zsum = 0
   for segment in range(len(path)):
      for vertex in range(len(path[segment])):
         x = path[segment][vertex][X3]
         y = path[segment][vertex][Y3]
         z = path[segment][vertex][Z3]
	 xsum += (x-xmean)**2
	 ysum += (y-ymean)**2
	 zsum += (z-zmean)**2
	 sum += 1
   xvar = xsum/sum
   yvar = ysum/sum
   zvar = zsum/sum
   [minimum,xindex,yindex,zindex,z] = min([xvar,Y3,Z3,X3,xmean],\
      [yvar,X3,Z3,Y3,ymean],[zvar,X3,Y3,Z3,zmean])
   return [xindex,yindex,zindex,z]

def project(path,xindex,yindex):
   #
   # return a 2D path projection
   #
   newpath = []
   for segment in range(len(path)):
      newpath.append([])
      for vertex in range(len(path[segment])):
         x = path[segment][vertex][xindex]
         y = path[segment][vertex][yindex]
	 newpath[segment].append([x,y,[]])
   return newpath

def lift(path,xindex,yindex,zindex,z):
   #
   # lift a 2D path into 3D
   #
   newpath = []
   for segment in range(len(path)):
      newpath.append([])
      for vertex in range(len(path[segment])):
         x = path[segment][vertex][X]
         y = path[segment][vertex][Y]
	 point = [[],[],[],[]]
	 point[xindex] = x
	 point[yindex] = y
	 point[zindex] = z
	 newpath[segment].append(point)
   return newpath         

def contour(event):
   global boundarys, toolpaths, contours
   #
   # contour boundary to find toolpath
   #
   print "contouring boundary ..."
   xyscale = float(sxyscale.get())
   undercut = float(sundercut.get())
   if (undercut != 0.0):
      print "   undercutting contour by",undercut
   N_contour = 1
   if (len(boundarys) == 1):
      #
      # 2D contour
      #
      toolpaths[0] = []
      for n in range(N_contour):
         toolrad = (n+1)*(float(sdia.get())/2.0-undercut)/xyscale
         contours[0] = displace(boundarys[0],toolrad)
         contours[0] = prune(contours[0],-1,event)
         toolpaths[0].extend(contours[0])
         plot(event)
   else:
      #
      # 3D contour
      #
      for layer in range(len(boundarys)):
         toolpaths[layer] = []
         contours[layer] = []
	 if (boundarys[layer] != []):
            [xindex,yindex,zindex,z] = orient(boundarys[layer])
            for n in range(N_contour):
               toolrad = (n+1)*(float(sdia.get())/2.0-undercut)/xyscale
	       path = project(boundarys[layer],xindex,yindex)
               contour = displace(path,toolrad)
               contour = prune(contour,-1,event)
	       contours[layer] = lift(contour,xindex,yindex,zindex,z)
               toolpaths[layer].extend(contours[layer])
               plot(event)
   print "   done"

def raster(event):
   global contours, boundarys, toolpaths,\
      xmin, xmax, ymin, ymax, zmin, zmax
   #
   # raster interiors
   #
   print "rastering interior ..."
   xyscale = float(sxyscale.get())
   tooldia = float(sdia.get())/xyscale
   if (len(boundarys) == 1):
      #
      # 2D raster
      #
      if (contours[0] == []):
         edgepath = boundarys[0]
         delta = tooldia/2.0
      else:
         edgepath = contours[0]
         delta = tooldia/4.0
      rasterpath = raster_area(edgepath,delta,ymin,ymax)
      toolpaths[0].extend(rasterpath)
   else:
      #
      # 3D raster
      #
      for layer in range(len(boundarys)):
         if (boundarys[layer] != []):
            if (contours[layer] == []):
               edgepath = boundarys[layer]
               delta = tooldia/2.0
            else:
               edgepath = contours[layer]
               delta = tooldia/4.0
            [xindex,yindex,zindex,z] = orient(edgepath)
            edgepath = project(edgepath,xindex,yindex)
            [min,max] = [[xmin,xmax],[ymin,ymax],[],[zmin,zmax]][yindex]
            rasterpath = raster_area(edgepath,delta,min,max)
	    rasterpath = lift(rasterpath,xindex,yindex,zindex,z)
            toolpaths[layer].extend(rasterpath)
            #plot(event)
            #raw_input(str(layer))
   plot(event)
   print "   done"

def raster_area(edgepath,delta,min,max):
   #
   # raster a 2D region
   #
   # find row-edge intersections
   #
   xyscale = float(sxyscale.get())
   overlap = float(soverlap.get())
   tooldia = float(sdia.get())/xyscale
   edges = []
   rasterpath = []
   dymin = min - 2*tooldia*overlap
   dymax = max + 2*tooldia*overlap
   row1 = int(floor((dymax-dymin)/(tooldia*overlap)))
   for row in range(row1+1):
      edges.append([])
   for seg in range(len(edgepath)):
      for vertex in range(len(edgepath[seg])-1):
	 x0 = edgepath[seg][vertex][X]
	 y0 = edgepath[seg][vertex][Y]
	 x1 = edgepath[seg][vertex+1][X]
	 y1 = edgepath[seg][vertex+1][Y]
	 if (y1 == y0):
	    continue
	 elif (y1 < y0):
	    x0, x1 = x1, x0
	    y0, y1 = y1, y0
	 row0 = int(ceil((y0 - dymin)/(tooldia*overlap)))
	 row1 = int(floor((y1 - dymin)/(tooldia*overlap)))
	 for row in range(row0,(row1+1)):
	    y = dymin + row*tooldia*overlap
	    x = x0*(y1-y)/(y1-y0) + x1*(y-y0)/(y1-y0)
	    edges[row].append(x)
   for row in range(len(edges)):
      edges[row].sort()
      y = dymin + row*tooldia*overlap
      edge = 0
      while edge < len(edges[row]):
	 x0 = edges[row][edge] + delta
	 edge += 1
	 if (edge < len(edges[row])):
	    x1 = edges[row][edge] - delta
         else:
	    print "shouldn't happen in raster:  row",row,"length",len(edges[row])
	    break
	 edge += 1
	 if (x0 < x1):
	    rasterpath.append([[x0,y,[]],[x1,y,[]]])
   return rasterpath

def zslice(event):
   global zmax
   #
   # slice object in z direction
   #
   xindex = X
   yindex = Y
   zindex = Z
   zscale = float(szscale.get())
   zoff = float(szmax.get()) - zmax*zscale
   ztop = float(sztop.get()) - zoff
   zbot = float(szbot.get()) - zoff
   dz = float(sthickness.get())
   slice(xindex,yindex,zindex,ztop,zbot,dz,event)

def slice(xindex,yindex,zindex,ztop,zbot,dz,event):
   global faces, vertices, boundarys, toolpaths, contours
   #
   # slice object
   #
   xyscale = float(sxyscale.get())
   nlayers = 2+int((ztop-zbot)/dz)
   boundarys = [[] for i in range(nlayers)]
   toolpaths = [[] for i in range(nlayers)]
   contours = [[] for i in range(nlayers)]
   #
   # find slice intersections
   #
   print "   slicing %d layers ..."%nlayers
   for face in range(len(faces)):
      for vertex in range(len(faces[face])):
         vertex0 = faces[face][vertex] - 1
	 p0 = [vertices[vertex0][X], vertices[vertex0][Y], \
	    vertices[vertex0][Z]]
	 if (vertex < (len(faces[face])-1)):
            vertex1 = faces[face][vertex+1] - 1
         else:
	    vertex1 = faces[face][0] - 1
	 p1 = [vertices[vertex1][X], vertices[vertex1][Y], \
	    vertices[vertex1][Z]]
	 if (p0[zindex] <  p1[zindex]):
	    direction = UP
	 else:
 	    direction = DOWN
	    [p0, p1] = [p1, p0]
	 layer0 = int(floor(.5+(ztop-p0[zindex])/dz))
	 layer1 = int(ceil(.5+(ztop-p1[zindex])/dz))
	 for layer in range(layer1,(layer0+1)):
	    if ((layer >= 0) & (layer < nlayers)):
	       p = [[],[],[]]
	       p[zindex] = ztop - (layer-.5)*dz
	       if (p1[zindex] != p0[zindex]):
	          p[xindex] = p0[xindex] + (p1[xindex]-p0[xindex]) * \
	             (p[zindex]-p0[zindex])/(p1[zindex]-p0[zindex])
	          p[yindex] = p0[yindex] + (p1[yindex]-p0[yindex]) * \
	             (p[zindex]-p0[zindex])/(p1[zindex]-p0[zindex])
	          boundarys[layer].append([p[X],p[Y],direction,p[Z]])
	       else:
	          p[xindex] = (p0[xindex] + p1[xindex])/2.0
	          p[yindex] = (p0[yindex] + p1[yindex])/2.0
	          boundarys[layer].append([p[X],p[Y],direction,p[Z]])
   #
   # find layer segments
   #
   for layer in range(len(boundarys)):
      boundary = []
      vertex = 0
      while vertex < len(boundarys[layer]):
         p0 = [boundarys[layer][vertex][X3], boundarys[layer][vertex][Y3], \
	    boundarys[layer][vertex][Z3]]
         direction = boundarys[layer][vertex][DIRECTION]
	 vertex += 1
         p1 = [boundarys[layer][vertex][X3], boundarys[layer][vertex][Y3], \
	    boundarys[layer][vertex][Z3]]
	 vertex += 1
	 if (direction == UP):
 	    boundary.append([[p0[X],p0[Y],[],p0[Z]],[p1[X],p1[Y],[],p1[Z]]])
	 else:
 	    boundary.append([[p1[X],p1[Y],[],p1[Z]],[p0[X],p0[Y],[],p0[Z]]])
      boundarys[layer] = boundary
      toolpaths[layer] = []
   #
   # sort segments
   #
   print "   sorting ..."
   for layer in range(len(boundarys)):
      if (len(boundarys[layer]) == 0):
         continue
      starts = []
      ends = []
      boundary = [[]]
      available = [TRUE for i in boundarys[layer]]
      for edge in range(len(boundarys[layer])):
         pstart = [boundarys[layer][edge][START][X3],\
	    boundarys[layer][edge][START][Y3],boundarys[layer][edge][START][Z3]]
         pend = [boundarys[layer][edge][END][X3],\
	    boundarys[layer][edge][END][Y3],boundarys[layer][edge][END][Z3]]
	 starts.append([pstart[xindex],pstart[yindex],edge])
	 ends.append([pend[xindex],pend[yindex],edge])
      starts.sort()
      ends.sort()
      end_index = [[] for i in starts]
      for index in range(len(starts)):
         end_index[ends[index][EDGE]] = index
      edge = start_edge = 0
      segment = 0
      boundary[segment].append([boundarys[layer][edge][START][X3],\
         boundarys[layer][edge][START][Y3],[],\
         boundarys[layer][edge][START][Z3]])
      available[edge] = FALSE
      while 1: 
         boundary[segment].append([boundarys[layer][edge][END][X3],\
            boundarys[layer][edge][END][Y3],[],\
            boundarys[layer][edge][END][Z3]])
         available[edge] = FALSE
         edge = starts[end_index[edge]][EDGE]
	 if (edge == start_edge):
	    if (available.count(TRUE) != 0):
	       start_edge = available.index(TRUE)
	       edge = start_edge
	       segment += 1
	       boundary.append([])
               boundary[segment].append([boundarys[layer][edge][START][X3],\
                  boundarys[layer][edge][START][Y3],[],\
                  boundarys[layer][edge][START][Z3]])
               available[edge] = FALSE
	    else:
	       break
      boundarys[layer] = boundary
   plot(event)

def extrude(event):
   global faces, vertices, zmax
   #
   # extrude 2D mesh -> 3D
   #
   print "extruding"
   #
   # copy and translate mesh
   #
   thickness = float(sextrude.get())
   nvertices = len(vertices)
   nfaces = len(faces)
   for face in range(nfaces):
      newface = []
      for vertex in range(len(faces[face])):
         newface.append(faces[face][vertex] + nvertices)
      faces.append(newface)
   for vertex in range(nvertices):
      x = vertices[vertex][X]
      y = vertices[vertex][Y]
      z = vertices[vertex][Z] + thickness
      vertices.append([x,y,z])
   plot(event)
   zmax += thickness

def write_RML():
   global boundarys, toolpaths, xmin, ymin, zmin, zmax
   #
   # RML (Modela-style HPGL) output
   #
   # Z x1,y1,z1,x2,y2,z2,...
   units = 1000
   xyscale = float(sxyscale.get())
   zscale = float(szscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   if (szup.get() == " "):
      izup = int(units*(ztop + .5*dz))
   else:
      izup = int(units*float(szup.get()))
   text = outfile.get()
   file = open(text, 'w')
   file.write("PA;PA;VS"+sxyvel.get()+";!VZ"+szvel.get()+";!MC1;")
   nsegment = 0
   for layer in range(len(boundarys)):
      if (toolpaths[layer] == []):
         path = boundarys[layer]
      else:
         path = toolpaths[layer]
      if (szdown.get() == " "):
         dz = float(sthickness.get())*zscale
         zoff = float(szmax.get()) - zmax*zscale
         ztop = float(sztop.get())
         izdown = int(units*(ztop - (layer-.5)*dz))
      else:
         izdown = int(units*float(szdown.get()))
      if (len(path) != 0):
         file.write("!PZ"+str(izdown)+","+str(izup)+";")
      for segment in range(len(path)):
         nsegment += 1
         vertex = 0
         x = int(units*(path[segment][vertex][X]*xyscale + xoff))
         y = int(units*(path[segment][vertex][Y]*xyscale + yoff))
         file.write("PU"+str(x)+","+str(y)+";")
         for vertex in range(1,len(path[segment])):
            x = int(units*(path[segment][vertex][X]*xyscale + xoff))
            y = int(units*(path[segment][vertex][Y]*xyscale + yoff))
            file.write("PD"+str(x)+","+str(y)+";")
   file.write("PU"+str(x)+","+str(y)+";!MC0;")
   #
   # file padding hack for end-of-file buffering problems
   #
   for i in range(750):
      file.write("!MC0;")
   file.close()
   print "wrote",nsegment,"RML toolpath segments to",text

def write_CAMM():
   global boundarys, toolpaths, xmin, ymin
   #
   # CAMM (CAMM-style cutter HPGL) output
   #
   units = 1000
   xyscale = float(sxyscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   text = outfile.get()
   file = open(text, 'w')
   file.write("PA;PA;!ST1;!FS"+sforce.get()+";VS"+svel.get()+";")
   nsegment = 0
   for layer in range(len(boundarys)):
      if (toolpaths[layer] == []):
         path = boundarys[layer]
      else:
         path = toolpaths[layer]
      for segment in range(len(path)):
         nsegment += 1
         vertex = 0
         x = int(units*(path[segment][vertex][X]*xyscale + xoff))
         y = int(units*(path[segment][vertex][Y]*xyscale + yoff))
         file.write("PU"+str(x)+","+str(y)+";")
         for vertex in range(1,len(path[segment])):
            x = int(units*(path[segment][vertex][X]*xyscale + xoff))
            y = int(units*(path[segment][vertex][Y]*xyscale + yoff))
            file.write("PD"+str(x)+","+str(y)+";")
   file.write("PU0,0;")
   file.close()
   print "wrote",nsegment,"CAMM toolpath segments to",text

def write_EPI():
   global boundarys, toolpaths, xmin, ymin, zmin, zmax, jobname
   #
   # Epilog lasercutter output
   # todo: try 1200 DPI
   #
   units = 600
   bedheight = float(sheight.get())
   xyscale = float(sxyscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   text = outfile.get()
   file = open(text, 'w')
   if (jobname == ""):
      jobname = outfile.get()
   if (iautofocus.get() == 0):
      #
      # init with autofocus off
      #
      file.write("%-12345X@PJL JOB NAME="+jobname+"\r\nE@PJL ENTER LANGUAGE=PCL\r\n&y0A&l0U&l0Z&u600D*p0X*p0Y*t600R*r0F&y50P&z50S*r6600T*r5100S*r1A*rC%1BIN;XR"+srate.get()+";YP"+spower.get()+";ZS"+sspeed.get()+";")
   else:
      #
      # init with autofocus on
      #
      file.write("%-12345X@PJL JOB NAME="+jobname+"\r\nE@PJL ENTER LANGUAGE=PCL\r\n&y1A&l0U&l0Z&u600D*p0X*p0Y*t600R*r0F&y50P&z50S*r6600T*r5100S*r1A*rC%1BIN;XR"+srate.get()+";YP"+spower.get()+";ZS"+sspeed.get()+";")
   nsegment = 0
   if (len(boundarys) > 1):
      zmaxpower = float(szmaxpower.get())
      zminpower = float(szminpower.get())
   for layer in range(len(boundarys)):
      if ((len(boundarys) > 1) & (len(boundarys[layer]) > 0)):
         #
	 # 3D file, set power from height
	 #
         z = boundarys[layer][0][0][Z3]
	 power = zminpower + (zmaxpower-zminpower)*(z-zmin)/(zmax-zmin)
	 file.write("YP%d;"%power)
      path = boundarys[layer]
      if (len(toolpaths) > layer):
         if (toolpaths[layer] != []):
            path = toolpaths[layer]
      for segment in range(len(path)):
         nsegment += 1
         vertex = 0
         x = int(units*(path[segment][vertex][X]*xyscale + xoff))
         y = int(units*(bedheight - (path[segment][vertex][Y]*xyscale + yoff)))
         file.write("PU"+str(x)+","+str(y)+";")
         for vertex in range(1,len(path[segment])):
            x = int(units*(path[segment][vertex][X]*xyscale + xoff))
            y = int(units*(bedheight - (path[segment][vertex][Y]*xyscale + yoff)))
            file.write("PD"+str(x)+","+str(y)+";")
   file.write("%0B%1BPUE%-12345X@PJL EOJ \r\n")
   file.close()
   print "wrote",nsegment,"Epilog toolpath segments to",text

def write_UNI():
   global boundarys, toolpaths, xmin, ymin
   #
   # Universal lasercutter output
   #
   units = 1000
   bedheight = float(sheight.get())
   xyscale = float(sxyscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   text = outfile.get()
   file = open(text, 'w')
   file.write("Z") # initialize
   file.write("t%s~;"%text) # title
   file.write("IN;DF;PS0;DT~") # initialize
   ppibyte = int(float(srate.get())/10)
   file.write("s%c"%ppibyte) # PPI
   speed_hibyte = int(648*float(sspeed.get()))/256
   speed_lobyte = int(648*float(sspeed.get()))%256
   # speed_hibyte = (648*int(sspeed.get()))/256
   # speed_lobyte = (648*int(sspeed.get()))%256
   file.write("v%c%c"%(speed_hibyte,speed_lobyte)) # speed
   power_hibyte = (320*int(spower.get()))/256
   power_lobyte = (320*int(spower.get()))%256
   file.write("p%c%c"%(power_hibyte,power_lobyte)) # power
   file.write("a%c"%2) # air assist on high
   nsegment = 0
   if (len(boundarys) > 1):
      zmaxpower = float(szmaxpower.get())
      zminpower = float(szminpower.get())
   for layer in range(len(boundarys)):
      if ((len(boundarys) > 1) & (len(boundarys[layer]) > 0)):
         #
	 # 3D file, set power from height
	 #
         z = boundarys[layer][0][0][Z3]
	 power = zminpower + (zmaxpower-zminpower)*(z-zmin)/(zmax-zmin)
	 power_hibyte = (320*int(power))/256
	 power_lobyte = (320*int(power))%256
	 file.write("p%c%c"%(power_hibyte,power_lobyte))
      path = boundarys[layer]
      if (len(toolpaths) > layer):
         if (toolpaths[layer] != []):
            path = toolpaths[layer]
      for segment in range(len(path)):
         nsegment += 1
         vertex = 0
         x = int(units*(path[segment][vertex][X]*xyscale + xoff))
         y = int(2000 + units*((17-bedheight) + (path[segment][vertex][Y]*xyscale + yoff)))
         file.write("PU;PA"+str(x)+","+str(y)+";PD;")
         for vertex in range(1,len(path[segment])):
            x = int(units*(path[segment][vertex][X]*xyscale + xoff))
            y = int(2000 + units*((17-bedheight) + (path[segment][vertex][Y]*xyscale + yoff)))
            file.write("PA"+str(x)+","+str(y)+";")
   file.write("e") # end of file
   file.close()
   print "wrote",nsegment,"Universal toolpath segments to",text

def write_G():
   global boundarys, toolpaths, xmin, ymin, zmin, zmax
   #
   # G code output
   #
   xyscale = float(sxyscale.get())
   zscale = float(sxyscale.get())
   dlayer = float(sthickness.get())/zscale
   feed = float(sfeed.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   cool = icool.get()
   text = outfile.get()
   file = open(text, 'w')
   file.write("%\n")
   file.write("O1234\n")
   file.write("T"+stool.get()+"M06\n") # tool
   file.write("G90G54\n") # absolute positioning with respect to set origin
   file.write("F%0.3f\n"%feed) # feed rate
   file.write("S"+sspindle.get()+"\n") # spindle speed
   if (cool == TRUE): file.write("M08\n") # coolant on
   file.write("G00Z"+szup.get()+"\n") # move up before starting spindle
   file.write("M03\n") # spindle on clockwise
   nsegment = 0
   for layer in range((len(boundarys)-1),-1,-1):
      if (toolpaths[layer] == []):
         path = boundarys[layer]
      else:
         path = toolpaths[layer]
      if (szdown.get() == " "):
         zdown = zoff + zmin + (layer-0.50)*dlayer
      else:
         zdown = float(szdown.get())
      for segment in range(len(path)):
         nsegment += 1
         vertex = 0
         x = path[segment][vertex][X]*xyscale + xoff
         y = path[segment][vertex][Y]*xyscale + yoff
         file.write("G00X%0.4f"%x+"Y%0.4f"%y+"Z"+szup.get()+"\n") # rapid motion
         file.write("G01Z%0.4f"%zdown+"\n") # linear motion
         for vertex in range(1,len(path[segment])):
            x = path[segment][vertex][X]*xyscale + xoff
            y = path[segment][vertex][Y]*xyscale + yoff
            file.write("X%0.4f"%x+"Y%0.4f"%y+"\n")
         file.write("Z"+szup.get()+"\n")
   file.write("G00Z"+szup.get()+"\n") # move up before stopping spindle
   file.write("M05\n") # spindle stop
   if (cool == TRUE): file.write("M09\n") # coolant off
   file.write("M30\n") # program end and reset
   file.write("%\n")
   file.close()
   print "wrote",nsegment,"G code toolpath segments to",text

def write_IMG():
   global boundarys, toolpaths, xmin, ymin
   #
   # bitmap image output
   #
   xyscale = float(sxyscale.get())
   xysize = float(sxysize.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   text = outfile.get()
   ximg = int(sximg.get())
   yimg = int(syimg.get())
   image = Image.new("RGB",[ximg,yimg],(0,0,0))
   draw = ImageDraw.Draw(image)
   nsegment = 0
   for layer in range(len(boundarys)):
      if (toolpaths[layer] == []):
         path = boundarys[layer]
      else:
         path = toolpaths[layer]
      for segment in range(len(path)):
         nsegment += 1
         vertex = 0
         x0 = int((path[segment][vertex][X]*xyscale + xoff)*ximg/xysize)
         y0 = yimg - int((path[segment][vertex][Y]*xyscale + yoff)*yimg/xysize)
         for vertex in range(1,len(path[segment])):
            x1 = int((path[segment][vertex][X]*xyscale + xoff)*ximg/xysize)
            y1 = yimg - int((path[segment][vertex][Y]*xyscale + yoff)*yimg/xysize)
   	    draw.line([(x0,y0),(x1,y1)],(255,255,255))
	    [x0,y0] = [x1,y1]
   image.save(text)
   print "wrote",nsegment,"toolpath segments to image",text

def write_ORD():
   global boundarys, toolpaths, xmin, ymin
   #
   # OMAX waterjet output
   #
   units = 1000
   xyscale = float(sxyscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   lead = float(slead.get())
   quality = int(squality.get())
   text = outfile.get()
   file = open(text, 'w')
   nsegment = 0
   for layer in range(len(boundarys)):
      if (toolpaths[layer] == []):
         path = boundarys[layer]
      else:
         path = toolpaths[layer]
      for segment in range(len(path)):
         nsegment += 1
         x0 = path[segment][0][X]*xyscale + xoff
         x1 = path[segment][1][X]*xyscale + xoff
	 dx = x1 - x0
         y0 = path[segment][0][Y]*xyscale + yoff
         y1 = path[segment][1][Y]*xyscale + yoff
	 dy = y1 - y0
	 nx = -dy
	 ny = dx
	 norm = sqrt(nx*nx + ny*ny)
	 nx = nx/norm
	 ny = ny/norm
	 xlead = x0 + nx*lead
	 ylead = y0 + ny*lead
         file.write("%f, %f, 0, %d\n"%(xlead,ylead,quality))
#         file.write("%f, %f, 0, 0\n"%(xlead,ylead))
         for vertex in range(0,(len(path[segment])-0)):
            x = path[segment][vertex][X]*xyscale + xoff
            y = path[segment][vertex][Y]*xyscale + yoff
            file.write("%f, %f, 0, %d\n"%(x,y,quality))
         xm1 = path[segment][-1][X]*xyscale + xoff
         xm2 = path[segment][-2][X]*xyscale + xoff
	 dx = xm2 - xm1
         ym1 = path[segment][-1][Y]*xyscale + yoff
         ym2 = path[segment][-2][Y]*xyscale + yoff
	 dy = ym2 - ym1
	 nx = -dy
	 ny = dx
	 norm = sqrt(nx*nx + ny*ny)
	 nx = nx/norm
	 ny = ny/norm
	 xlead = xm1 - nx*lead*.9
	 ylead = ym1 - ny*lead*.9
#         file.write("%f, %f, 0, %d\n"%(xlead,ylead,quality))
         file.write("%f, %f, 0, 0\n"%(xlead,ylead))
   file.close()
   print "wrote",nsegment,"ORD toolpath segments to",text

def write_STL():
   global faces, vertices, xmin, ymin, zmax
   #
   # STL output
   #
   text = outfile.get()
   file = open(text, 'w')
   file.write("solid\n")
   xyscale = float(sxyscale.get())
   zscale = float(szscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   zoff = float(szmax.get()) - zmax*zscale
   #
   # scale vertices
   #
   for vertex in range(len(vertices)):
      x = vertices[vertex][X]*xyscale + xoff
      y = vertices[vertex][Y]*xyscale + yoff
      z = vertices[vertex][Z]*zscale + zoff
      vertices[vertex] = [x,y,z]
   #
   # write file
   #
   nfaces = len(faces)
   for face in range(nfaces):
      #
      # find normal
      #
      [x0,y0,z0] = vertices[faces[face][0]-1]
      [x1,y1,z1] = vertices[faces[face][1]-1]
      [x2,y2,z2] = vertices[faces[face][2]-1]
      """
      [nx,ny,nz] = [-x0, -y1, -z2]
      [d1x,d1y,d1z] = [x1-x0, y1-y0, z1-z0]
      d1 = d1x*d1x + d1y*d1y + d1z*d1z
      nd1 = nx*d1x + ny*d1y + nz*d1z
      [nx,ny,nz] = [nx-nd1*d1x/d1, ny-nd1*d1y/d1, nz-nd1*d1z/d1]
      [d2x,d2y,d2z] = [x2-x0, y2-y0, z2-z0]
      d2d1 = d2x*d1x + d2y*d1y + d2z*d1z
      [d2x,d2y,d2z] = [d2x-d2d1*d1x/d1, d2y-d2d1*d1y/d1, d2z-d2d1*d1z/d1]
      d2 = d2x*d2x + d2y*d2y + d2z*d2z
      nd2 = nx*d2x + ny*d2y + nz*d2z
      [nx,ny,nz] = [nx-nd2*d2x/d2, ny-nd2*d2y/d2, nz-nd2*d2z/d2]
      n = sqrt(nx*nx + ny*ny + nz*nz)
      [nx,ny,nz] = [nx/n, ny/n, nz/n]
      """
      [nx,ny,nz] = [0,0,0]
      #
      # write
      #
      file.write("   facet normal %f %f %f\n"%(nx,ny,nz))
      file.write("      outer loop\n")
      file.write("         vertex %f %f %f\n"%(x0,y0,z0))
      file.write("         vertex %f %f %f\n"%(x1,y1,z1))
      file.write("         vertex %f %f %f\n"%(x2,y2,z2))
      file.write("      endloop\n")
      file.write("   endfacet\n")
      if (len(faces[face]) == 4):
         #
         # triangulate square face
         #
         [x3,y3,z3] = vertices[faces[face][3]-1]
         file.write("   facet normal %f %f %f\n"%(nx,ny,nz))
         file.write("      outer loop\n")
         file.write("         vertex %f %f %f\n"%(x0,y0,z0))
         file.write("         vertex %f %f %f\n"%(x2,y2,z2))
         file.write("         vertex %f %f %f\n"%(x3,y3,z3))
         file.write("      endloop\n")
         file.write("   endfacet\n")
   file.write("endsolid\n")
   file.close()
   print "wrote",nfaces,"STL facets to",text

def write_OMS():
   global boundarys, toolpaths, xmin, ymin
   #
   # Resonetics excimer micromachining center output
   #
   units = 25.4
   pulseperiod = float(spulseperiod.get())
   cutvel = float(scutvel.get())
   cutaccel = float(scutaccel.get())
   slewvel = 1
   slewaccel = 5
   settle = 100
   xyscale = float(sxyscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   text = outfile.get()
   file = open(text, 'w')
   file.write("AA LP0,0,0,0,0\n") # set origin
   file.write("PP%d\n"%pulseperiod) # set pulse period
   nsegment = 0
   for layer in range(len(boundarys)):
      if (toolpaths[layer] == []):
         path = boundarys[layer]
      else:
         path = toolpaths[layer]
      for segment in range(len(path)):
         nsegment += 1
         vertex = 0
         x = units*(path[segment][vertex][X]*xyscale + xoff)
         y = units*(path[segment][vertex][Y]*xyscale + yoff)
	 file.write("VL%.1f,%.1f\n"%(slewvel,slewvel))
	 file.write("AC%.1f,%.1f\n"%(slewaccel,slewaccel))
         file.write("MA%f,%f\n"%(x,y))
	 file.write("VL%.1f,%.1f\n"%(cutvel,cutvel))
	 file.write("AC%.1f,%.1f\n"%(cutaccel,cutaccel))
	 file.write("WT%d\n"%settle) # wait to settle
         for vertex in range(1,len(path[segment])):
            x = units*(path[segment][vertex][X]*xyscale + xoff)
            y = units*(path[segment][vertex][Y]*xyscale + yoff)
            file.write("CutAbs %f,%f\n"%(x,y))
   file.write("END\n")
   file.close()
   print "wrote",nsegment,"Resonetics toolpath segments to",text

def write_DXF():
   global boundarys, toolpaths, xmin, xmax, ymin, ymax
   #
   # DXF output
   #
   print xmin, xmax, ymin, ymax
   xyscale = float(sxyscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   text = outfile.get()
   file = open(text, 'w')
   file.write("999\nDXF written by cam.py\n")
   file.write("0\nSECTION\n")
   file.write("2\nHEADER\n")
   file.write("9\n$EXTMIN\n")
   file.write("10\n%f\n"%(xmin*xyscale+xoff))
   file.write("20\n%f\n"%(ymin*xyscale+yoff))
   file.write("9\n$EXTMAX\n")
   file.write("10\n%f\n"%(xmax*xyscale+xoff))
   file.write("20\n%f\n"%(ymax*xyscale+yoff))
   file.write("0\nENDSEC\n")
   file.write("0\nSECTION\n")
   file.write("2\nTABLES\n")
   file.write("0\nTABLE\n")
   file.write("2\nLTYPE\n70\n1\n")
   file.write("0\nLTYPE\n")
   file.write("2\nCONTINUOUS\n")
   file.write("70\n64\n3\n")
   file.write("Solid line\n")
   file.write("72\n65\n73\n0\n40\n0.000000\n")
   file.write("0\nENDTAB\n")
   file.write("0\nTABLE\n2\nLAYER\n70\n1\n")
   file.write("0\nLAYER\n2\ndefault\n70\n64\n62\n7\n6\n")
   file.write("CONTINUOUS\n0\nENDTAB\n")
   file.write("0\nENDSEC\n")
   file.write("0\nSECTION\n")
   file.write("2\nBLOCKS\n")
   file.write("0\nENDSEC\n")
   file.write("0\nSECTION\n")
   file.write("2\nENTITIES\n")
   nsegment = 0
   for layer in range(len(boundarys)):
      if (toolpaths[layer] == []):
         path = boundarys[layer]
      else:
         path = toolpaths[layer]
      for segment in range(len(path)):
         nsegment += 1
         for vertex in range(1,len(path[segment])):
            x0 = path[segment][vertex-1][X]*xyscale + xoff
            y0 = path[segment][vertex-1][Y]*xyscale + yoff
            x1 = path[segment][vertex][X]*xyscale + xoff
            y1 = path[segment][vertex][Y]*xyscale + yoff
	    file.write("0\nLINE\n")
	    file.write("10\n%f\n"%x0)
	    file.write("20\n%f\n"%y0)
	    file.write("11\n%f\n"%x1)
	    file.write("21\n%f\n"%y1)
   file.write("0\nENDSEC\n")
   file.write("0\nEOF\n")
   file.close()
   print "wrote",nsegment,"DXF toolpath segments to",text

def write(event):
   global xmin, xmax, ymin, ymax, zmin, zmax
   #
   # write toolpath
   #
   text = outfile.get()
   if (find(text,".rml") != -1):
      write_RML()
   elif (find(text,".camm") != -1):
      write_CAMM()
   elif (find(text,".epi") != -1):
      write_EPI()
   elif (find(text,".uni") != -1):
      write_UNI()
   elif (find(text,".g") != -1):
      write_G()
   elif ((find(text,".jpg") != -1) | (find(text,".bmp") != -1)):
      write_IMG()
   elif (find(text,".ord") != -1):
      write_ORD()
   elif (find(text,".stl") != -1):
      write_STL()
   elif (find(text,".oms") != -1):
      write_OMS()
   elif (find(text,".dxf") != -1):
      write_DXF()
   elif (find(text,".stl") != -1):
      write_STL()
   else:
      print "unsupported output file format"
      return
   xyscale = float(sxyscale.get())
   xoff = float(sxmin.get()) - xmin*xyscale
   yoff = float(symin.get()) - ymin*xyscale
   print "   xmin: %0.3g "%(xmin*xyscale+xoff),\
      "xmax: %0.3g "%(xmax*xyscale+xoff),\
      "dx: %0.3g "%((xmax-xmin)*xyscale)
   print "   ymin: %0.3g "%(ymin*xyscale+yoff),\
      "ymax: %0.3g "%(ymax*xyscale+yoff), \
      "dy: %0.3g "%((ymax-ymin)*xyscale)

def delframes():
   #
   # delete all CAM frames
   #
   intext = infile.get()
   if ((find(intext,".cmp") != -1) | (find(intext,".CMP")!= -1) \
      | (find(intext,".sol")!= -1) | (find(intext,".SOL") != -1) \
      | (find(intext,".via")!= -1) | (find(intext,".VIA")!= -1)
      | (find(intext,".mill")!= -1) | (find(intext,".MILL")!= -1)):
      unionbtn.pack_forget()
   else:
      unionbtn.pack()
   camframe.pack_forget()
   cutframe.pack_forget()
   imgframe.pack_forget()
   toolframe.pack_forget()
   feedframe.pack_forget()
   zcoordframe.pack_forget()
   z2Dframe.pack_forget()
   zsliceframe.pack_forget()
   gframe.pack_forget()
   laserframe.pack_forget()
   excimerframe.pack_forget()
   autofocusframe.pack_forget()
   jetframe.pack_forget()
   out3Dframe.pack_forget()

def camselect(event):
   global faces, xmin, xmax, ymin, ymax, zmin, zmax, xysize, zsize, fixed_size
   #
   # pack appropriate CAM GUI options based on output file
   #
   xyscale = float(sxyscale.get())
   zscale = float(szscale.get())
   outtext = outfile.get()
   if (find(outtext,".rml") != -1):
      delframes()
      camframe.pack()
      if (not fixed_size):
         sxysize.set("8")
         szsize.set("8")
      sxyvel.set("4")
      szvel.set("4")
      if (faces != []):
	 sztop.set(str(zmax))
	 szbot.set(str(zmin))
         sthickness.set(str(zmax-zmin))
	 zsliceframe.pack()
      if ((faces != []) | (len(boundarys) > 1)):
         szsize.set(sxysize.get())
	 zcoordframe.pack()
      else:
         szup.set("0.05")
         szdown.set("-0.005")
         z2Dframe.pack()
      sdia.set("0.0156")
      sundercut.set("0.00")
      soverlap.set("0.8")
      feedframe.pack()
      toolframe.pack()
   elif (find(outtext,".camm") != -1):
      delframes()
      camframe.pack()
      if (not fixed_size):
         sxysize.set("6")
         szsize.set("6")
      if (faces != []):
	 sztop.set(str(zmax))
	 szbot.set(str(zmin))
         sthickness.set(str(zmax-zmin))
	 zsliceframe.pack()
      if ((faces != []) | (len(boundarys) > 1)):
	 zcoordframe.pack()
      sforce.set("45")
      svel.set("2")
      sdia.set("0.01")
      sundercut.set("0.005")
      soverlap.set("1.0")
      toolframe.pack()
      cutframe.pack()
   elif (find(outtext,".epi") != -1):
      delframes()
      camframe.pack()
      if (not fixed_size):
         sxysize.set("24")
         szsize.set("24")
      if (faces != []):
	 sztop.set(str(zmax))
	 szbot.set(str(zmin))
         sthickness.set(str(zmax-zmin))
	 zsliceframe.pack()
      if ((faces != []) | (len(boundarys) > 1)):
	 zcoordframe.pack()
         laserzframe.pack()
      sheight.set("10")
      srate.set("2500")
      spower.set("50")
      sspeed.set("50")
      laserframe.pack()
      sdia.set("0.01")
      sundercut.set("0.00")
      soverlap.set("0.8")
      autofocusframe.pack()
      toolframe.pack()
   elif (find(outtext,".uni") != -1):
      delframes()
      camframe.pack()
      if (not fixed_size):
         sxysize.set("24")
         szsize.set("24")
      if (faces != []):
	 sztop.set(str(zmax))
	 szbot.set(str(zmin))
         sthickness.set(str(zmax-zmin))
	 zsliceframe.pack()
      if ((faces != []) | (len(boundarys) > 1)):
	 zcoordframe.pack()
         laserzframe.pack()
      sheight.set("18")
      srate.set("500")
      spower.set("10")
      sspeed.set("10")
      laserframe.pack()
      sdia.set("0.01")
      sundercut.set("0.00")
      soverlap.set("0.8")
      toolframe.pack()
   elif (find(outtext,".g") != -1):
      delframes()
      camframe.pack()
      if (not fixed_size):
         sxysize.set("24")
         szsize.set("24")
      sxyvel.set("2")
      szvel.set("2")
      if (faces != []):
	 sztop.set(str(zmax))
	 szbot.set(str(zmin))
         sthickness.set(str(zmax-zmin))
	 zsliceframe.pack()
      if ((faces != []) | (len(boundarys) > 1)):
	 zcoordframe.pack()
      else:
         szup.set("0.05")
         szdown.set("-0.005")
         z2Dframe.pack()
      sdia.set("0.0156")
      sundercut.set("0.00")
      soverlap.set("0.8")
      toolframe.pack()
      sfeed.set("5")
      sspindle.set("5000")
      stool.set("1")
      gframe.pack()
   elif ((find(outtext,".jpg") != -1) | (find(outtext,".bmp") != -1)):
      delframes()
      camframe.pack()
      sdia.set("0.015")
      sundercut.set("0.00")
      soverlap.set("0.8")
      toolframe.pack()
      sximg.set("500")
      syimg.set("500")
      imgframe.pack()
      xysize = float(sxysize.get())
      if ((xmax-xmin) > (ymax-ymin)):
         xyscale = xysize/(xmax - xmin)
         sxyscale.set(str(xyscale))
         xoff = -(xmin*xysize)/(xmax-xmin)
	 yoff = -(ymin*xysize)/(xmax-xmin)
         sxmin.set(str(xoff))
         symin.set(str(yoff))
      else:
         xyscale = xysize/(ymax - ymin)
         sxyscale.set(str(xyscale))
         yoff = -(ymin*xysize)/(ymax-ymin)
         xoff = -(xmin*xysize)/(ymax-ymin)
         sxmin.set(str(xoff))
         symin.set(str(yoff))
   elif (find(outtext,".ord") != -1):
      delframes()
      camframe.pack()
      if (faces != []):
	 sztop.set(str(zmax))
	 szbot.set(str(zmin))
         sthickness.set(str(zmax-zmin))
	 zsliceframe.pack()
      if ((faces != []) | (len(boundarys) > 1)):
	 zcoordframe.pack()
      if (not fixed_size):
         sxysize.set("24")
      sdia.set("0.01")
      sundercut.set("0.005")
      soverlap.set("1.0")
      toolframe.pack()
      slead.set("0.1")
      squality.set("-3")
      jetframe.pack()
   elif (find(outtext,".oms") != -1):
      delframes()
      camframe.pack()
      if (faces != []):
	 sztop.set(str(zmax))
	 szbot.set(str(zmin))
         sthickness.set(str(zmax-zmin))
	 zsliceframe.pack()
      if ((faces != []) | (len(boundarys) > 1)):
	 zcoordframe.pack()
      if (not fixed_size):
         sxysize.set("1")
      spulseperiod.set("10000")
      scutvel.set("0.1")
      scutaccel.set("5.0")
      excimerframe.pack()
      sdia.set(".001")
      sundercut.set("0.00")
      soverlap.set("0.8")
      toolframe.pack()
   elif (find(outtext,".dxf") != -1):
      delframes()
      sdia.set("0.0156")
      sundercut.set("0.00")
      soverlap.set("0.8")
      camframe.pack()
      toolframe.pack()
   elif (find(outtext,".stl") != -1):
      delframes()
      sthickness.set("0.1")
      out3Dframe.pack()
      zcoordframe.pack()
   else:
      print "output file format not supported"
#   plot(event)
   plot_delete(event)
   return

def devselect(event):
   #
   # select the output device
   #
   sel = wdevlist.get(wdevlist.curselection())
   cur_sel = outfile.get()
   dot = find(cur_sel,'.')
   cur_sel = cur_sel[(dot+1):]
   if ((sel[0:3] == 'epi') & (cur_sel != 'epi')):
      outfile.set('out.epi')
      camselect(0)
   elif ((sel[0:3] == 'oms') & (cur_sel != 'oms')):
      outfile.set('out.oms')
      camselect(0)
   elif ((sel[0:3] == 'ord') & (cur_sel != 'ord')):
      outfile.set('out.ord')
      camselect(0)
   elif ((sel[0:2] == 'g:') & (cur_sel != 'g')):
      outfile.set('out.g')
      camselect(0)
   elif ((sel[0:3] == 'bmp') & (cur_sel != 'bmp')):
      outfile.set('out.bmp')
      camselect(0)
   elif ((sel[0:3] == 'jpg') & (cur_sel != 'jpg')):
      outfile.set('out.jpg')
      camselect(0)
   elif ((sel[0:3] == 'stl') & (cur_sel != 'stl')):
      outfile.set('out.stl')
      camselect(0)
   elif ((sel[0:3] == 'dxf') & (cur_sel != 'dxf')):
      outfile.set('out.dxf')
      camselect(0)
   elif ((sel[0:3] == 'uni') & (cur_sel != 'uni')):
      outfile.set('out.uni')
      camselect(0)
   elif ((sel[0:3] == 'rml') & (cur_sel != 'rml')):
      outfile.set('out.rml')
      camselect(0)
   elif ((sel[0:4] == 'camm') & (cur_sel != 'camm')):
      outfile.set('out.camm')
      camselect(0)
   
def send(event):
   #
   # send to the output device
   #
   outtext = outfile.get()
   if (find(outtext,".rml") != -1):
      wdevbtn.config(text="sending ...")
      wdevbtn.update()
      write(event)
      print os.system('stty 9600 raw -echo crtscts </dev/ttyS0')
      print os.system('cat %s > /dev/ttyS0'%outtext)
      print os.system('rm %s'%outtext)
      wdevbtn.config(text="send to")
      #wdevbtn.update()
   elif (find(outtext,".camm") != -1):
      wdevbtn.config(text="sending ...")
      wdevbtn.update()
      write(event)
      print os.system('stty 9600 raw -echo crtscts </dev/ttyS0')
      print os.system('cat %s > /dev/ttyS0'%outtext)
      print os.system('rm %s'%outtext)
      wdevbtn.config(text="send to")
      #wdevbtn.update()
   elif (find(outtext,".epi") != -1):
      wdevbtn.config(text="sending ...")
      wdevbtn.update()
      write(event)
      print os.system('lpr -P Queue %s'%outtext)
      print os.system('rm %s'%outtext)
      wdevbtn.config(text="send to")
      #wdevbtn.update()
   else:
      print "output not configured for",outtext

def openfile():
   #
   # dialog to select an input file
   #
   filename = askopenfilename()
   infile.set(filename)
   read(0)

def savefile():
   #
   # dialog to select an output file
   #
   filename = asksaveasfilename()
   outfile.set(filename)
   camselect(0)

root = Tk()
root.title('cam.py')
root.bind('Q','exit')

print "cam.py "+DATE+" (c) MIT CBA Neil Gershenfeld"
print """Permission granted for experimental and personal use;
   license for commercial sale available from MIT"""
print prompt

#
# parse input command line arguments
#
infile = StringVar()
infile.set('')
outfile = StringVar()
outfile.set('out.epi')
xmin = 0.0
xmax = 0.0
ymin = 0.0
ymax = 0.0
zmin = -1.0
zmax = 0.0
xyscale = 1.0
zscale = 1.0
xysize = 1.0
zsize = 1.0
nverts = 10
fixed_size = False
jobname = ""
for i in range(len(sys.argv)):
   if (find(sys.argv[i],"-o") != -1):
      outfile.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-d") != -1):
      xysize = float(sys.argv[i+1])
      fixed_size = True
   elif (find(sys.argv[i],"-p") != -1):
      xyscale = float(sys.argv[i+1])
   elif (find(sys.argv[i],"-x") != -1):
      xmin = float(sys.argv[i+1])
   elif (find(sys.argv[i],"-y") != -1):
      ymin = float(sys.argv[i+1])
   elif (find(sys.argv[i],"-i") != -1):
      infile.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-n") != -1):
      noise_flag = 0
   elif (find(sys.argv[i],"-#") != -1):
      nverts = int(sys.argv[i+1])
   elif (find(sys.argv[i],"-j") != -1):
      jobname = sys.argv[i+1]
if (len(sys.argv) > 1):
   if (sys.argv[1][0] != '-'):
      infile.set(sys.argv[1])
sxmin = StringVar()
sxmin.set(str(xmin))
symin = StringVar()
symin.set(str(ymin))
szmax = StringVar()
szmax.set(str(zmax))
sxyscale = StringVar()
sxyscale.set(str(xyscale))
szscale = StringVar()
szscale.set(str(zscale))
sxysize = StringVar()
sxysize.set(str(xysize))
szsize = StringVar()
szsize.set(str(zsize))
#
# define GUI
#
inframe = Frame(root)
inbtn = Button(inframe, text="input file:",command=openfile)
inbtn.pack(side="left")
winfile = Entry(inframe, width=15, textvariable=infile)
winfile.pack(side="left")
winfile.bind('<Return>',read)
Label(inframe, text=" ").pack(side="left")
Label(inframe, text="xy display size:").pack(side="left")
wxysize = Entry(inframe, width=4, textvariable=sxysize)
wxysize.pack(side="left")
wxysize.bind('<Return>',plot)
Label(inframe, text=" scale:").pack(side="left")
autobtn = Button(inframe, text="auto")
autobtn.bind('<Button-1>',autoscale)
autobtn.pack(side="left")
fixedbtn = Button(inframe, text="fixed")
fixedbtn.bind('<Button-1>',fixedscale)
fixedbtn.pack(side="left")
Label(inframe, text=" ").pack(side="left")
ivert = IntVar()
wvert = Checkbutton(inframe, text="show vertices", variable=ivert)
#wvert.pack(side="left")
#wvert.bind('<ButtonRelease-1>',plot)
inframe.pack()
#
xycoordframe = Frame(root)
Label(xycoordframe, text=" x min:").pack(side="left")
wxmin = Entry(xycoordframe, width=6, textvariable=sxmin)
wxmin.pack(side="left")
wxmin.bind('<Return>',plot)
Label(xycoordframe, text=" y min:").pack(side="left")
wymin = Entry(xycoordframe, width=6, textvariable=symin)
wymin.pack(side="left")
wymin.bind('<Return>',plot)
Label(xycoordframe, text=" xy scale factor:").pack(side="left")
wxyscale = Entry(xycoordframe, width=6, textvariable=sxyscale)
wxyscale.pack(side="left")
wxyscale.bind('<Return>',plot_delete)
sdxy = StringVar()
Label(xycoordframe, textvariable=sdxy).pack(side="left")
xycoordframe.pack()
#
zcoordframe = Frame(root)
Label(zcoordframe, text="z max: ").pack(side="left")
wzmax = Entry(zcoordframe, width=6, textvariable=szmax)
wzmax.bind('<Return>',plot)
wzmax.pack(side="left")
Label(zcoordframe, text="z scale factor:").pack(side="left")
wzscale = Entry(zcoordframe, width=6, textvariable=szscale)
wzscale.bind('<Return>',plot)
wzscale.pack(side="left")
Label(zcoordframe, text="z display size:").pack(side="left")
wzsize = Entry(zcoordframe, width=6, textvariable=szsize)
wzsize.bind('<Return>',plot)
wzsize.pack(side="left")
sdz = StringVar()
Label(zcoordframe, textvariable=sdz).pack(side="left")
zcoordframe.pack()
#
canvasframe = Frame(root)
xscrollbar = Scrollbar(canvasframe, orient=HORIZONTAL)
xscrollbar.grid(row=1, column=0, sticky=E+W)
yscrollbar = Scrollbar(canvasframe)
yscrollbar.grid(row=0, column=1, sticky=N+S)
c = Canvas(canvasframe, width=WINDOW, height=WINDOW, background='white',
   xscrollcommand=xscrollbar.set, yscrollcommand=yscrollbar.set)
c.grid(row=0, column=0, sticky=N+S+E+W)
c.configure(scrollregion=(0,0,WINDOW,WINDOW))
xscrollbar.config(command=c.xview)
yscrollbar.config(command=c.yview)
canvasframe.pack()
#
outframe = Frame(root)
#
Logo = Canvas(outframe, width=26, height=26, background="white")
Logo.create_oval(2,2,8,8,fill="red",outline="")
Logo.create_rectangle(11,2,17,8,fill="blue",outline="")
Logo.create_rectangle(20,2,26,8,fill="blue",outline="")
Logo.create_rectangle(2,11,8,17,fill="blue",outline="")
Logo.create_oval(10,10,16,16,fill="red",outline="")
Logo.create_rectangle(20,11,26,17,fill="blue",outline="")
Logo.create_rectangle(2,20,8,26,fill="blue",outline="")
Logo.create_rectangle(11,20,17,26,fill="blue",outline="")
Logo.create_rectangle(20,20,26,26,fill="blue",outline="")
Logo.pack(side="left")
status = StringVar()
namedate = "   cam.py ("+DATE+")  "
status.set(namedate)
Label(outframe, textvariable=status).pack(side="left")
outbtn = Button(outframe, text="output file:",command=savefile)
outbtn.pack(side="left")
woutfile = Entry(outframe, width=15, textvariable=outfile)
woutfile.bind('<Return>',camselect)
woutfile.pack(side="left")
Label(outframe, text=" ").pack(side="left")
Button(outframe, text="quit", command='exit').pack(side="left")
Label(outframe, text=" ").pack(side="left")
outframe.pack()
#
devframe = Frame(root)
wdevbtn = Button(devframe, text="send to")
wdevbtn.bind('<Button-1>',send)
wdevbtn.pack(side="left")
Label(devframe, text=" output device: ").pack(side="left")
wdevscroll = Scrollbar(devframe,orient=VERTICAL)
wdevlist = Listbox(devframe,width=40,height=1,yscrollcommand=wdevscroll.set)
wdevlist.bind('<ButtonRelease-1>',devselect)
wdevscroll.config(command=wdevlist.yview)
wdevscroll.pack(side=RIGHT,fill='y')
wdevlist.insert(END,"epi: Epilog lasercutter")
wdevlist.insert(END,"oms: Resonetics excimer micromachining center")
wdevlist.insert(END,"ord: OMAX waterjet cutter")
wdevlist.insert(END,"g: G code file")
wdevlist.insert(END,"bmp: image")
wdevlist.insert(END,"jpg: image")
wdevlist.insert(END,"stl: object")
wdevlist.insert(END,"dxf: drawing")
wdevlist.insert(END,"uni: Universal lasercutter")
wdevlist.insert(END,"rml: Roland Modela NC mill")
wdevlist.insert(END,"camm: Roland CAMM vinyl cutter")
wdevlist.pack(side=LEFT,fill=BOTH)
wdevlist.select_set(0)
devframe.pack()
#
camframe = Frame(root)
contourbtn = Button(camframe, text="contour boundary")
contourbtn.bind('<Button-1>',contour)
contourbtn.pack(side="left")
Label(camframe, text=" ").pack(side="left")
rasterbtn = Button(camframe, text="raster interior")
rasterbtn.bind('<Button-1>',raster)
rasterbtn.pack(side="left")
Label(camframe, text=" ").pack(side="left")
writebtn = Button(camframe, text="write toolpath")
writebtn.bind('<Button-1>',write)
writebtn.pack(side="left")
Label(camframe, text=" ").pack(side="left")
unionbtn = Button(camframe, text="union polygons")
unionbtn.bind('<Button-1>',union_boundary)
unionbtn.pack(side="left")
camframe.pack()
#
toolframe = Frame(root)
Label(toolframe, text="tool diameter: ").pack(side="left")
sdia = StringVar()
wtooldia = Entry(toolframe, width=6, textvariable=sdia)
wtooldia.pack(side="left")
wtooldia.bind('<Return>',plot_delete)
#Label(toolframe, text=" N contour: ").pack(side="left")
#sncontour = StringVar()
#wncontour = Entry(toolframe, width=3, textvariable=sncontour)
#wncontour.pack(side="left")
#wncontour.bind('<Return>',plot_delete)
Label(toolframe, text=" contour undercut: ").pack(side="left")
sundercut = StringVar()
wundercut = Entry(toolframe, width=6, textvariable=sundercut)
wundercut.pack(side="left")
wundercut.bind('<Return>',plot_delete)
Label(toolframe, text=" raster overlap: ").pack(side="left")
soverlap = StringVar()
woverlap = Entry(toolframe, width=6, textvariable=soverlap)
woverlap.pack(side="left")
woverlap.bind('<Return>',plot_delete)
#
feedframe = Frame(root)
Label(feedframe, text=" xy speed:").pack(side="left")
sxyvel = StringVar()
Entry(feedframe, width=10, textvariable=sxyvel).pack(side="left")
Label(feedframe, text=" z speed:").pack(side="left")
szvel = StringVar()
Entry(feedframe, width=10, textvariable=szvel).pack(side="left")
#
z2Dframe = Frame(root)
Label(z2Dframe, text="z up:").pack(side="left")
szup = StringVar()
Entry(z2Dframe, width=10, textvariable=szup).pack(side="left")
Label(z2Dframe, text=" z down:").pack(side="left")
szdown = StringVar()
Entry(z2Dframe, width=10, textvariable=szdown).pack(side="left")
#
zsliceframe = Frame(root)
zslicebtn = Button(zsliceframe, text="z slice")
zslicebtn.bind('<Button-1>',zslice)
zslicebtn.pack(side="left")
Label(zsliceframe, text=" ").pack(side="left")
Label(zsliceframe, text=" top: ").pack(side="left")
sztop = StringVar()
sztop.set("0")
wztop = Entry(zsliceframe, width=10, textvariable=sztop)
wztop.pack(side="left")
Label(zsliceframe, text=" bottom: ").pack(side="left")
szbot = StringVar()
szbot.set("-1")
wzbot = Entry(zsliceframe, width=10, textvariable=szbot)
wzbot.pack(side="left")
Label(zsliceframe, text=" thickness: ").pack(side="left")
sthickness = StringVar()
sthickness.set("1")
wthickness = Entry(zsliceframe, width=10, textvariable=sthickness)
wthickness.pack(side="left")
#
gframe = Frame(root)
Label(gframe, text=" feed rate:").pack(side="left")
sfeed = StringVar()
Entry(gframe, width=6, textvariable=sfeed).pack(side="left")
Label(gframe, text=" spindle speed:").pack(side="left")
sspindle = StringVar()
Entry(gframe, width=6, textvariable=sspindle).pack(side="left")
Label(gframe, text=" tool:").pack(side="left")
stool = StringVar()
Entry(gframe, width=3, textvariable=stool).pack(side="left")
icool = IntVar()
wcool = Checkbutton(gframe, text="coolant", variable=icool)
wcool.pack(side="left")
#
cutframe = Frame(root)
Label(cutframe, text="force: ").pack(side="left")
sforce = StringVar()
Entry(cutframe, width=10, textvariable=sforce).pack(side="left")
Label(cutframe, text=" velocity:").pack(side="left")
svel = StringVar()
Entry(cutframe, width=10, textvariable=svel).pack(side="left")
#
laserframe = Frame(root)
Label(laserframe, text="bed height: ").pack(side="left")
sheight = StringVar()
Entry(laserframe, width=10, textvariable=sheight).pack(side="left")
Label(laserframe, text=" rate: ").pack(side="left")
srate = StringVar()
Entry(laserframe, width=10, textvariable=srate).pack(side="left")
Label(laserframe, text=" power:").pack(side="left")
spower = StringVar()
Entry(laserframe, width=10, textvariable=spower).pack(side="left")
Label(laserframe, text=" speed:").pack(side="left")
sspeed = StringVar()
Entry(laserframe, width=10, textvariable=sspeed).pack(side="left")
#
laserzframe = Frame(root)
Label(laserzframe, text="z max power: ").pack(side="left")
szmaxpower = StringVar()
szmaxpower.set("100")
Entry(laserzframe, width=3, textvariable=szmaxpower).pack(side="left")
Label(laserzframe, text="%     z min power: ").pack(side="left")
szminpower = StringVar()
szminpower.set("0")
Entry(laserzframe, width=3, textvariable=szminpower).pack(side="left")
Label(laserzframe, text="%").pack(side="left")
#
autofocusframe = Frame(root)
iautofocus = IntVar()
wautofocus = Checkbutton(autofocusframe, text="Auto Focus", variable=iautofocus).pack(side="left")
#
imgframe = Frame(root)
Label(imgframe, text="x size (pixels): ").pack(side="left")
sximg = StringVar()
Entry(imgframe, width=10, textvariable=sximg).pack(side="left")
Label(imgframe, text=" y size (pixels):").pack(side="left")
syimg = StringVar()
Entry(imgframe, width=10, textvariable=syimg).pack(side="left")
#
jetframe = Frame(root)
Label(jetframe,text="lead-in/out: ").pack(side="left")
slead = StringVar()
wlead = Entry(jetframe, width=4, textvariable=slead)
wlead.pack(side="left")
Label(jetframe,text="quality: ").pack(side="left")
squality = StringVar()
wquality = Entry(jetframe, width=4, textvariable=squality)
wquality.pack(side="left")
#
excimerframe = Frame(root)
Label(excimerframe,text="pulse period (usec): ").pack(side="left")
spulseperiod = StringVar()
wpulseperiod = Entry(excimerframe, width=5, textvariable=spulseperiod)
wpulseperiod.pack(side="left")
Label(excimerframe,text="cut velocity: ").pack(side="left")
scutvel = StringVar()
wcutvel = Entry(excimerframe, width=4, textvariable=scutvel)
wcutvel.pack(side="left")
Label(excimerframe,text="cut acceleration: ").pack(side="left")
scutaccel = StringVar()
wcutaccel = Entry(excimerframe, width=4, textvariable=scutaccel)
wcutaccel.pack(side="left")
#
out3Dframe = Frame(root)
extrudebtn = Button(out3Dframe, text="extrude")
extrudebtn.bind('<Button-1>',extrude)
extrudebtn.pack(side="left")
Label(out3Dframe,text="thickness: ").pack(side="left")
sextrude = StringVar()
wextrude = Entry(out3Dframe, width=6, textvariable=sextrude)
wextrude.pack(side="left")
Label(out3Dframe,text=" ").pack(side="left")
write3Dbtn = Button(out3Dframe, text="write file")
write3Dbtn.bind('<Button-1>',write)
write3Dbtn.pack(side="left")
#
faces = []
contours = [[]]
boundarys = [[]]
toolpaths = [[]]
slices = [[]]
#
# read input file and set up GUI
#
if (infile.get() != ''):
   read(0)
else:
   camselect(0)
#
# parse output command line arguments
#
for i in range(len(sys.argv)):
   if (find(sys.argv[i],"-f") != -1):
      sforce.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-v") != -1):
      svel.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-t") != -1):
      sdia.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-a") != -1):
      srate.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-e") != -1):
      spower.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-s") != -1):
      sspeed.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-h") != -1):
      sheight.set(sys.argv[i+1])
   elif (find(sys.argv[i],"-c") != -1):
      contour(0)
   elif (find(sys.argv[i],"-r") != -1):
      raster(0)
   elif (find(sys.argv[i],"-w") != -1):
      write(0)
      sys.exit()
#
# start GUI
#
root.mainloop()
