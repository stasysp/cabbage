pip3 install git+https://github.com/stasysp/cabbage.git
pip3 install git+https://github.com/stasysp/pak.git
pip3 install git+https://github.com/stasysp/cselect.git
pip3 install git+https://github.com/stasysp/pppr.git

mkdir build
(cd build && cmake .. && make -j8)

if [ ! -d "deepmatching_bin" ]; then
    mkdir deepmatching_bin
    (cd deepmatching_bin && wget http://lear.inrialpes.fr/src/deepmatching/code/deepmatching_1.2.2.zip && unzip deepmatching_1.2.2.zip)
fi

python build_settings.py