#!/usr/bin/perl

# History
#
# 22 Jun 08 Created

use Image::Magick;
use English;
use strict;

my $input = $ARGV[0];
my $output = $ARGV[1];

# Image width in mm
my $width = $ARGV[2] + 0;

0 == $width and
    die "Width must be specified in mm";

-f $input or
    die "Could not find file '$input'";

my $image = Image::Magick->new();

my $error;
$error = $image->Read($input) and
    die "Could not read input file '$input' $error\n";

my $widthPixels = $image->Get('width');
my $heightPixels = $image->Get('height');

# Size of a pixel in mm
my $pixelSize = $width / $widthPixels;


sub header() {
    print OUTPUT "G94\n";   # Units per minute mode
    print OUTPUT "F4000\n";  # Feed rate
    print OUTPUT "G97\n";   # Spindle RPM Mode
    print OUTPUT "S20\n"; # Spindle RPM
    print OUTPUT "G40\n";   # Cutter radius compensation off
    print OUTPUT "G21\n";   # set units to mm
    print OUTPUT "G64 P0.1\n";	# Blend mode, can divert by 0.1mm from programmed position, required for path blending
    print OUTPUT "M3\n";	# Enable laser
}

sub penDown() {
#    print OUTPUT "M3\n";
    print OUTPUT "M62 P0\n";
}

sub penUp() {
#    print OUTPUT "M5\n";
    print OUTPUT "M63 P0\n";
}

sub outputRow($$$) {
    my $row = $ARG[0];
    my $start = $ARG[1];
    my $end = $ARG[2];

    printf (OUTPUT "G00 X%.4f Y%.4f \n", $start * $pixelSize, $row * $pixelSize);
    penDown();
    printf (OUTPUT "G01 X%.4f Y%.4f \n", $end * $pixelSize, $row * $pixelSize);
    penUp();
}

sub footer() {
    print OUTPUT "M2\n";
}


open(OUTPUT, ">$output") or
    die "Could not open output file '$output' for writing";

print('There are ', $image->Get('colors'), " colors in the image\n");

if ($image->Get('colors') != 2) {
	print("Dithering image\n");
	$image->Quantize(colors => 2, colorspace=>'gray', dither => 1);
}

header();

my @pixel;

for (my $y = 0; $y < $heightPixels; $y++) {
    ($y % 50) or
	print "Processing row $y out of $heightPixels\n";

    my $lineStart = -1;
    my $lineEnd;
    my $realX;

    for (my $x = 0; $x < $widthPixels; $x++) {
# Bidirectional burning, rather than returning back to the left
	if ($y % 2) {
	    $realX = $widthPixels - $x;
	} else {
	    $realX = $x;
	}

	@pixel = $image->getPixel(x =>$realX, y => $y);

#	print("Currently at $realX, $y, Colour is ", join(',', @pixel), "\n");

	if ($pixel[0] != 1) {
#	    print("Currently at $realX, $y, Colour is ", join(',', @pixel), "\n");
	    if (-1 == $lineStart) {
		$lineStart = $realX;
	    }
	    $lineEnd = $realX;
	} elsif (-1 != $lineStart) {
	    outputRow ($heightPixels - $y, $lineStart, $lineEnd + 1);
	    $lineStart = -1;
	}
    }

    if (-1 != $lineStart) {
	outputRow ($heightPixels - $y, $lineStart, $lineEnd + 1);
	$lineStart = -1;  
    }
}

footer();

close(OUTPUT);

