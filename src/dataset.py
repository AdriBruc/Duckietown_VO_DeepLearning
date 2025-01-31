import os
from torch.utils.data import Dataset, DataLoader
from os import walk
import numpy as np
from torchvision import transforms
import pandas as pd
from PIL import Image
from .utils import absolute2relative
import matplotlib.pyplot as plt

from .dataset_split import train_dummy, val_dummy, test_dummy

pd.set_option("max_colwidth", None)


class DuckietownDataset(Dataset):

    def __init__(self, data_dic, args):
        # numpy array: filepath + img_name, x, y, theta, theta_correct
        self.data = pd.DataFrame()
        for i in range(len(data_dic["filenames"])):
            # read .txt file
            gt_file = pd.read_fwf(args["data_dir"] + data_dic["filenames"][i])
            # get list of all files in dir
            all_filenames_dir = sorted(next(walk(args["data_dir"] + data_dic["dir"][i]), (None, None, []))[2])
            full_path = np.array(
                [os.path.join(str(args["data_dir"] + data_dic["dir"][i]), xi) for xi in all_filenames_dir])
            # print(i, data_dic["filenames"][i], gt_file.shape, len(all_filenames_dir))
            gt_file["img"] = full_path
            print(data_dic["filenames"][i], data_dic["idx"][i][0], data_dic["idx"][i][0])
            # only use images with idx
            start_idx = data_dic["idx"][i][0]
            end_idx = data_dic["idx"][i][1]
            if (end_idx - start_idx) % args["trajectory_length"] != 0:
                end_idx = end_idx - ((end_idx - start_idx) % args["trajectory_length"])
                # print(start_idx, end_idx)
            gt_file = gt_file.loc[start_idx:end_idx]
            self.data = self.data.append(gt_file, ignore_index=True)

        self.trajectory_length = args["trajectory_length"]
        self.transform = transforms.Compose([
            transforms.Resize((args["resize"] // 2, args["resize"])),
            transforms.ToTensor(),
            # transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
            # The following means and stds have been pre-computed
            # transforms.Normalize(mean=[0.424, 0.459, 0.218], std=[0.224, 0.215, 0.158])
        ])
        print("final shape", self.data.shape, "batches", (len(self.data) - 1) // self.trajectory_length,
              "trajectory_length", args["trajectory_length"])

    def __len__(self):
        return (len(self.data) - 1) // self.trajectory_length

    def __getitem__(self, idx):
        images_stacked = []
        rel_poses = []
        # start and end index of trajectory
        start_idx = idx * self.trajectory_length
        end_idx = (idx + 1) * self.trajectory_length
        for i in range(start_idx, end_idx):
            # for first image load both
            if i == start_idx:
                data1 = self.data.iloc[i][["x", "y", "theta_correct", "img"]]
                img1 = Image.open(data1["img"]).convert('RGB')
                img1 = self.preprocess(img1)

            data2 = self.data.iloc[i + 1][["x", "y", "theta_correct", "img"]]
            img2 = Image.open(data2["img"]).convert('RGB')
            img2 = self.preprocess(img2)
            # print(i, start_idx, end_idx, data1["img"][-15:], data2["img"][-15:])

            pose1 = data1[["x", "y", "theta_correct"]].to_numpy()
            pose2 = data2[["x", "y", "theta_correct"]].to_numpy()

            absolute_poses = np.vstack((pose1, pose2))
            rel_pose = absolute2relative(absolute_poses).squeeze()

            # axis=1: images are next to each other, axis=0: images are behind
            images_stacked.append(np.concatenate([img1, img2], axis=0))  # trajectory_length * (3, 640, 640)
            rel_poses.append(rel_pose)

            data1 = data2
            img1 = img2
        images_stacked = np.asarray(images_stacked)
        rel_poses = np.asarray(rel_poses)
        return images_stacked, rel_poses

    def preprocess(self, img):
        area = (0, 160, 640, 480)
        img = img.crop(area)
        img = self.transform(img)
        return img

    def get_absolute_poses(self):
        return self.data[["x", "y", "theta_correct"]]

class DuckietownDatasetCTC(DuckietownDataset):
    def __init__(self, data_dic, args):
        super().__init__(data_dic, args)

    def __len__(self):
        return len(self.data) // self.trajectory_length

    def __getitem__(self, idx):
        images = []
        
        # start and end index of trajectory
        start_idx = idx * self.trajectory_length
        end_idx = (idx + 1) * self.trajectory_length
        for i in range(start_idx, end_idx):
            data1 = self.data.iloc[i][["x", "y", "theta_correct", "img"]]
            img1 = Image.open(data1["img"]).convert('RGB')
            img1 = self.preprocess(img1)
            images.append(np.array(img1))
        images = np.asarray(images)
        return images

if __name__ == "__main__":

    args = {"data_dir": "/Users/julia/Documents/UNI/Master/Montréal/AV/project/duckietown_visual_odometry/data/",
            "train_split": train_dummy, "val_split": val_dummy, "test_split": test_dummy,
            "checkpoint_path": './checkpoint', "checkpoint": None, "bsize": 2, "lr": 0.001,
            "weight_decay": 1e-4, "trajectory_length": 5, "dropout_p": 0.85,
            "resize": 64, "K": 100, "epochs": 5, "patience": 40}

    test_dataset = DuckietownDataset(args["train_split"], args)

    test_loader = DataLoader(test_dataset, batch_size=args["bsize"], shuffle=True, drop_last=True)

    # get some random training images
    dataiter = iter(test_loader)

    for i in range(5):
        img_stacked, rel_pos = dataiter.next()
        for i in img_stacked:
            for j in i:
                print(j.min(), j.max())
                j = j.permute(1, 2, 0)
                plt.imshow(j[:, :, :3])
                plt.show()
                plt.imshow(j[:, :, 3:])
                plt.show()
        print(img_stacked.shape, rel_pos.shape)
        # break
