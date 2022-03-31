===
Forked by sdeux
===
Writer: chiesa 
Date: March 31, 2020
Copyright Alpes Lasers SA, Neuchatel, Switzerland
Driver for the Alpes Lasers S-2 pulser. Visit https://www.alpeslasers.ch/ for more informations.
Github: https://github.com/alpeslasers/sdeux

Usage
-----
See also the examples basic.py in the sdeux package folder.

Custom
-----
this is Alpes Laser S2 Voltage Source API.
API version exist each gen4, gen5, gen2005, etc..

I used gen5 api for my equipments.
Also for customizing Alpes laser S2 UI, i used some python packages.

-----
Need to PIP Package
- Pyinstaller
- Pyqt5 : recommend version 5.13
- sdeux :aples laser driver

-----
Build
if you want to build customized UI, use this command

pyinstaller my_app.spec --onefile

builded .exe file will be exported in dist folder.
