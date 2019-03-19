import numpy as np
from time import time
from os import makedirs, listdir, remove
from os.path import join, isfile, isdir, exists, splitext
from cabbage.features.GenerateFeatureVector import pairwise_features
from cabbage.data.video import VideoData
from cabbage.features.ReId import get_element
from time import time
from keras.applications.vgg16 import preprocess_input
import cabbage.features.spatio as st
from cabbage.regression.Regression import get_default_W
from cabbage.features.deepmatching import ReadOnlyDeepMatching
from cabbage.features.ReId import StackNet64x64
from cabbage.features.deepmatching import DeepMatching
import json
import subprocess
from cabbage.features.combined import AABBLookup, gen_feature_batch

def execute_multiple_people_tracking(video_folder, X, Dt, video_name, dmax, settings_file,
    batch_size=700):
    """ this function runs the code end-to-end

        video_folder: {string} location where the video frames are stored as images
        X: {np.array} (n,h,w,3) video data
        Dt: {np.array} (m,6) detections [ (frame, x, y, w, h, score), ... ]
        video_name: {string} name of the video (can be any string, this is used
                             to later re-identify the data
        settings_file: {string} location of the settings file
        batch_size: {int} how large the chunks of pairs are that are processed
                            at the same time. Small values work on CPU's as well.
    """
    assert dmax <= 100, 'Currently no larger dmax value than 100 is allowed!'
    assert len(X.shape) == 4 and X.shape[3] == 3
    assert len(Dt.shape) == 2 and Dt.shape[1] == 6
    assert isdir(video_folder)
    assert isfile(settings_file)

    Settings = json.load(open(settings_file))

    data_root = Settings['data_root']
    deep_matching_binary = Settings['deepmatch']
    graph_solver = Settings['graph_solver']

    assert isfile(deep_matching_binary), 'the deepmatching binary must exist'

    if not isdir(data_root):
        makedirs(data_root)

    W = get_default_W(data_root, dmax)

    dm = DeepMatching(deep_matching_binary, data_root, dmax)
    dm.generate_matches(video_folder, video_name)

    reid = StackNet64x64(data_root)

    gg = BatchGraphGenerator(data_root, reid, dm, dmax, video_name)
    gg.build(Dt, X, W, batch_size=batch_size)
    edge_file, lifted_edge_file, config_file = gg.get_file_names()
    output_file = join(data_root, 'output.txt')

    args = (graph_solver, edge_file, lifted_edge_file, config_file, output_file)
    popen = subprocess.Popen(args, stdout=subprocess.PIPE)
    popen.wait()




class BatchGraphGenerator:
    """
    """

    def __init__(self, root, reid, dm, dmax, video_name):
        """
        """
        self.data_loc = join(root, 'BATCH_GG_' + video_name + "_dmax_" + str(dmax))
        if not isdir(self.data_loc):
            makedirs(self.data_loc)
        self.reid = reid
        self.dmax = dmax
        self.video_name = video_name
        self.dm = dm


    def build(self, Dt, X, W, batch_size=500):
        """ build the graph
            Dt: {np.array} detections for the video
                -> [(frame, x, y, w, h, score), ...]

            X: {np.array} (n, w, h, 3) video of the detections
        """
        dmax = self.dmax
        lifted_edge_start = int(dmax/2)

        __start = time()
        lookup = AABBLookup(Dt, X)
        __end = time()
        print('create lookup structure, elapsed:', __end - __start)

        n, _ = Dt.shape

        ALL_PAIRS = lookup.get_all_pairs(dmax)

        reid = self.reid
        dm = self.dm
        video_name = self.video_name


        edge_file, lifted_edge_file, config_file = self.get_file_names()
        EDGE_FILE = open(edge_file, "w")
        LIFTED_EDGE_FILE = open(lifted_edge_file, "w")

        with open(config_file, 'w+') as f:
            print(str(n), file=f)

        for _i in range(0, len(ALL_PAIRS), batch_size):
            __start = time()
            batch = ALL_PAIRS[_i:_i+batch_size]

            delta, edge_weights, i_, j_ = gen_feature_batch(
                batch, lookup, dmax, dm, reid, W, video_name)

            for i, j, w, d in zip(i_, j_, edge_weights, delta):
                #w = -1 * w
                if d < lifted_edge_start:
                    txt = str(i) + " " + str(j) + " " + str(w) + "\n"
                    EDGE_FILE.write(txt)
                    EDGE_FILE.flush()
                else:
                    txt = str(i) + " " + str(j) + " " + str(max(w, 0)) + "\n"
                    LIFTED_EDGE_FILE.write(txt)
                    LIFTED_EDGE_FILE.flush()

            __end = time()
            print('finish batch ' + str(_i) + ' .. ' + str(_i+batch_size) + \
                " total:" + str(len(ALL_PAIRS)) + " ... elapsed:" + \
                    str(__end - __start))


        EDGE_FILE.close()
        LIFTED_EDGE_FILE.close()

    def get_file_names(self):
        """
        """
        edge_file = join(self.data_loc, "edges.txt")
        lifted_edge_file = join(self.data_loc, "lifted_edges.txt")
        config_file = join(self.data_loc, "config.txt")
        return edge_file, lifted_edge_file, config_file




class GraphGenerator:
    """
    """


    def __init__(self, root, video, detections, dmax, W, d=None,
        video_name=None, DM_object=None, reid_object=None,
        is_memorized_reid=False):
        """
            root: {string} path to data root
            detections: {np.array} ([f, x, y, w, h, score], ...)
            dmax: {int}
            W: {np.array} calculated theta scores

        """
        if d is None:
            d = int(dmax/2)
        assert dmax > d
        #assert W.shape[0] == dmax

        if video_name is None:
            video_name = "video" + str(time)

        self.root = root
        self.X = video
        self.dmax = dmax
        self.d = d
        self.detections = detections
        self.video_name = video_name

        data_loc = self.get_data_folder()
        if not isdir(data_loc):
            makedirs(data_loc)

        n, _ = self.detections.shape
        #edges = []
        #lifted_edges = []

        start_i, edges, lifted_edges = self.load_edges(data_loc)

        ALL_EDGES = []

        gen = pairwise_features(self.root,None,
            DM_object=DM_object, reid_object=reid_object)

        vd = VideoData(detections)
        is_ordered = vd.is_ordered
        #is_ordered = self.check_if_detections_are_ordered(detections)

        #for i, entry in enumerate(self.detections):
        for i in range(start_i+1, n):
            __START = time()
            frame1, x1, y1, w1, h1,conf1 = detections[i]
            I1 = self.X[int(frame1-1)]
            for j in range(i+1, n):
                frame2, x2, y2, w2, h2,conf2 = detections[j]
                delta = int(abs(frame2-frame1) )
                if delta >= dmax :
                    if is_ordered:
                        break
                    else:
                        continue

                I2 = self.X[int(frame2-1)]

                try:
                    i1 = i if is_memorized_reid else None
                    i2 = j if is_memorized_reid else None
                    vec = gen.get_pairwise_vector(
                            video_name ,
                            I1, I2,
                            frame1,frame2,
                            (x1, y1, w1, h1),
                            (x2, y2, w2, h2),
                            conf1,
                            conf2,
                            i1=i1, i2=i2)

                    cost = -1 * (W[delta]@np.array(vec))

                    if delta > d:
                        if (cost > 0):
                            # lifted edge
                            lifted_edges.append((i,j,cost))
                    else:
                        # normal edge
                        edges.append((i,j,cost))

                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as e:
                    print("ignore frame " + str(frame1) + " -> " + str(frame2) \
                        +' because ' + str(e) + ' ... delta:' + str(delta))
                #print('cost:', cost)
                #cost = 10 if pid == pid_o else -1
            __END = time()
            print("edges for detection: ",i," out of ",n)
            print("\t\telapsed:", __END - __START)

            # --- store the data ---
            self.save_edges(i, data_loc, edges, lifted_edges)

            edge_OLD, lifted_edges_OLD = self.get_backup_file_names(i-1, data_loc)
            if isfile(edge_OLD):
                remove(edge_OLD)
            if isfile(lifted_edges_OLD):
                remove(lifted_edges_OLD)


        edges = np.array(edges)
        lifted_edges = np.array(lifted_edges)

        print('Edges', edges.shape)
        print('Lifted Edges', lifted_edges.shape)


        with open('config.txt', 'w+') as f:
            print(str(n), file=f)

        fmt = '%d %d %f'
        np.savetxt('edges.txt', edges, delimiter=';', fmt=fmt)
        np.savetxt('lifted_edges.txt', lifted_edges, delimiter=';', fmt=fmt)


    def get_backup_file_names(self, i, backup_loc):
        """
        """
        edge_file = join(backup_loc, "edges_%06d" % (i,) + '.npy')
        lifted_edge_file = join(backup_loc, "lifted_edges_%06d" % (i,) + '.npy')
        return edge_file, lifted_edge_file


    def get_i(self, backup_loc):
        edges = sorted([f for f in listdir(backup_loc) if
            f.startswith('edges') and f.endswith('.npy')])
        if len(edges) > 0:
            last_edge = edges[-1]
            return int(last_edge[6:12])
        else:
            return -1


    def load_edges(self, backup_loc):
        """
        """
        i = self.get_i(backup_loc)
        if i > 0:
            edge_file, lifted_edge_file = self.get_backup_file_names(i, backup_loc)
            assert isfile(edge_file)
            edges = np.load(edge_file).tolist()

            if isfile(lifted_edge_file):
                lifted_edges = np.load(lifted_edge_file).tolist()

        else:
            edges = []
            lifted_edges = []

        return i, edges, lifted_edges


    def save_edges(self, i, backup_loc, edges, lifted_edges):
        """
        """
        edge_file, lifted_edge_file = self.get_backup_file_names(i, backup_loc)
        assert len(edges) > 0
        np.save(edge_file, edges)

        if len(lifted_edges) > 0:
            np.save(lifted_edge_file, lifted_edges)


    # def check_if_detections_are_ordered(self, detections):
    #     """ Yields true if the list of detections is ordered
    #     """
    #     n, _ = detections.shape
    #     for i in range(1, n):
    #         frame1, x1, y1, w1, h1,conf1 = detections[i-1]
    #         frame2, x2, y2, w2, h2,conf2 = detections[i]
    #         if frame2 < frame1:
    #             return False
    #     return True

    def get_data_folder(self):
        """ gets the data directory
        """
        return join(join(self.root, 'graph_generator'), self.video_name)
