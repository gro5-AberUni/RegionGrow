---
title: 'The Region Growing Plugin (RegionGrow)'
tags:
  - QGIS
  - Region Growing
  - GIS
  - Remote Sensing
  - Python
authors:
  - name: Gregory Oakes^[Corresponding Author]
    orchid: 0000-0002-5054-1548
    affiliation: 1
  - name: Andy Hardy
    orchid: 0000-0002-7928-8873
    affiliation: 1
  - name: Yussuf Said Yussuf
    affiliation: "2, 3"
affiliations:
  - name: Department of Geography and Earth Sciences, Aberystwyth University, Aberystwyth SY23 3DB, UK
    index: 1
  - name: The State University of Zanzibar (SUZA), Tunguu, P.O.Box 146, Zanzibar
    index: 2
  - name: Tanzania Flying Labs
    index: 3
date: 21-04-2021
bibliography: references.bib

---

# Summary

In the fields of image analysis, computer vision and remote sensing
there are a number of instances where the digitisation of features by
the human operator is needed to develop mapped products or for
generating training data for classification routines. This process is
notoriously time consuming, labour intensive and error prone and, as
such, the manual digitisation of features in operational projects is
often unfeasible, particularly in time-sensitive applications like near
real-time monitoring applications, emergency response mapping or where
applications are made at a continental or global scape. Consequently,
there is a need for a simple to use region growing tool that can be used
to speed up the digitisation process and minimise human error.

We present a new Region Growing plugin tool (RegionGrow) for the open
source Geographical Information System software QGIS. RegionGrow is
designed to be user-friendly, computationally efficient, freely
available, with functionality to accommodate a variety of sources of
multiband remotely sensed imagery. By selecting a pixel in the centre of
an object of interest, e.g. a forest, water body etc, RegionGrow
generates connects pixels with a similar colour based on its Euclidean
distance with a L\*A\*B transformed colour space. This rapidly speeds up
the manual digitising process and minimises error.

![Overview of the processing steps performed by RegionGrow](Figure1.png){width="3.937007874015748in"
height="5.369911417322835in"}

# Statement of Need

Within the open source software domain, there is just one region growing tool available from within the Semi-Automatic Classification (SAC) QGIS plugin [@Cogendo2021]. However, this is intended to be used within the SAC classification workflow and cannot be used intuitively for other digitising needs. 

An independent region growing tool is needed for two primary reasons: 1) Where users wish to collect training data for conducting image classifications outside of the SAC plugin tool, for instance, taking advantage of the most current and robust machine learning solutions from within Python libraries like TPOT [@olson2016tpot] or Scikit-Learn [@pedregosa2011scikit]. 2) Where users wish to extract thematic information directly rather than following a classification routine. 

# Ongoing Projects

The RegionGrow QGIS plugin tool was originally developed for use within
the project: Spatial Intelligence System (SIS) for precision larviciding
based in Zanzibar, United Republic of Tanzania. Here, UAV technology is
being used to map pools of water where malarial mosquitoes breed. By
mapping these targets, they can be located by ground teams and treated
with low-toxicity larvicide in an effort to reduce the malarial mosquito
population. Although high resolution images (\<10 cm) of areas of
interest can be produced rapidly using UAVs, identifying and digitising
water body features is a laborious and error-strewn process. Using
RegionGrow, non-GIS specialists can now rapidly and accurately digitise
these features, supplying vital information to ground-teams
significantly quicker than following a conventional manual digitising
approach (on average four times quicker).

# Using this Software

**Step 1.**

Remotely sensed imagery (e.g. UAV/satellite imagery) is loaded into
QGIS, ensuring that it is projected into a coordinate system (with map
units in metres), e.g. Universal Transverse Mercator (UTM).

Input RGB imagery (typically acquired using commercially available UAV
platforms) is converted into an *L\*A\*B* colour space, where colour is
represented by a luminosity channel (*l*), the colour on a red -- green
axis (*a*) and a blue-yellow axis (*b*) [@rathore2012colour; @baldevbhai2012color; @pandy2017rgblab]. The LAB colour space can help account for
the uneven distribution of RGB values within the colour image [@niu2014image]. Other imagery, i.e. multispectral optical imagery or radar
backscatter imagery, do not undergo colour transformation.

![a) Example RGB Drone imagery. b) The same drone imagery converted into an L\*A\*B* colour space.](Figure2.png){width="3.937007874015748in"
height="5.369911417322835in"}

An output vector filename is defined by the user before continuing to
the next step.

**Step 2.**

The user selects/clicks on a point of interest within the image. The
coordinates of the selected point is retrieved and a square
neighbourhood created (based on a user defined distance).

![a). Location of user click within RGB drone imagery. B) L\*A\*B* transformed drone imagery and the location of the user clicked location. C) Local neighbourhood around in this case 25m around the user clicked location within the drone imagery. ](Figure3.png){width="3.937007874015748in"
height="2.6625in"}

**Step 3.**

All pixels within the neighbourhood are plotted into a 3D feature space.
The Euclidean colour distance between each pixel and the selected pixel
is determined. Pixels with a lower colour distance are considered to be
of a similar colour.

![3D feature space showing pixels within the local area of the
user clicked location. The cross within the plot marks the user clicked
pixel.](Figure4.png){width="3.937007874015748in"
height="2.984346019247594in"}

![a) RGB Drone Imagery, b) L\*A\*B\* transformed drone imagery and
the location of the user clicked location. C) Euclidean distance within
the 3D feature space between the user selected pixels and all pixels
within the local neighbourhood of pixels.](Figure5.png){width="3.937007874015748in"
height="3.6587412510936135in"}

A spatial weighting is also applied where pixels geographically further
from the selected pixel have a lower weighting.

**Step 4.**

The colour distance and spatial distance are summed and pixels with a
combined value greater than the user defined threshold are masked out,
leaving only pixels considered to have a similar enough colour to be
joined into the same region.

**Step 5.**

The output region (pixels of similar colour) are vectorised where they
intersect the originally selected pixel, i.e. they must be joined to the
selected pixel.

**Step 6.**

The geometry of this feature is then simplified, broken geometries fixed
and holes within the feature are filled, and a buffer applied if defined
by the user. The final region is committed to an output vector dataset
(e.g. ESRI Shapefile, GeoJSON) as the digitised feature.

![a) Pixels are selected where the colour distance is less than a
user defined threshold. 6b) Selected pixels are vectorised and the
feature which directly intersects the user clicked location is selected
and simplified (c).](Figure6.png){width="3.937007874015748in"
height="3.5722451881014874in"}


# Dependencies

There are no dependencies required for the RegionGrow QGIS plugin tool beyond the dependencies required and installed by QGIS.

# Funding

This Software Development was funded by the Bill and Melinda Gates Foundation Innovation Fund INV-010583 through a grant managed by the Innovative Vector Control Consortium (IVCC) and the Aberystwyth
University Doctoral training programme.

# References
