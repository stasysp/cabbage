<<<<<<< HEAD
pip3 install git+https://github.com/justayak/cabbage.git
pip3 install git+https://github.com/justayak/pak.git
pip3 install git+https://github.com/justayak/cselect.git
pip3 install git+https://github.com/justayak/pppr.git
=======
pip install git+https://github.com/justayak/cabbage.git
pip install git+https://github.com/justayak/pak.git
pip install git+https://github.com/justayak/cselect.git
pip install git+https://github.com/justayak/pppr.git
>>>>>>> d7c73556e97d2b11770bfe8513d6153223375c44

mkdir build
(cd build && cmake .. && make -j8)

if [ ! -d "deepmatching_bin" ]; then
    mkdir deepmatching_bin
    (cd deepmatching_bin && wget http://lear.inrialpes.fr/src/deepmatching/code/deepmatching_1.2.2.zip && unzip deepmatching_1.2.2.zip)
fi

<<<<<<< HEAD
=======

>>>>>>> d7c73556e97d2b11770bfe8513d6153223375c44
python build_settings.py
