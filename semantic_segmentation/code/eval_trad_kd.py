%matplotlib inline
import torch
import torch.nn as nn
from torchvision import transforms
from torch.utils.data import DataLoader
import torch.nn.functional as F
import models
import matplotlib.pyplot as plt
from helper import *
torch.cuda.set_device(0)

classes = ['sky', 'building', 'pole', 'road', 'pavement', 'tree', 'signsymbol', 'fence', 'car', 'pedestrian', 'bicyclist', 'unlabelled']
DATA_DIR = '../data/CamVid/'

x_train_dir = os.path.join(DATA_DIR, 'train')
y_train_dir = os.path.join(DATA_DIR, 'trainannot')

x_valid_dir = os.path.join(DATA_DIR, 'val')
y_valid_dir = os.path.join(DATA_DIR, 'valannot')

x_test_dir = os.path.join(DATA_DIR, 'test')
y_test_dir = os.path.join(DATA_DIR, 'testannot')

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean = [0.41189489566336, 0.4251328133025, 0.4326707089857], std = [0.27413549931506, 0.28506257482912, 0.28284674400252])
])

train_dataset = CamVid(
    x_train_dir,
    y_train_dir,
    classes = classes,
    transform = transform
)

valid_dataset = CamVid(
    x_valid_dir,
    y_valid_dir,
    classes = classes, 
    transform = transform
)

test_dataset = CamVid(
    x_test_dir,
    y_test_dir,
    classes = classes, 
    transform = transform
)

trainloader = DataLoader(train_dataset, batch_size = 8, shuffle = True, drop_last = True)
valloader = DataLoader(valid_dataset, batch_size = 1, shuffle = False)
testloader = DataLoader(test_dataset, batch_size = 1, shuffle = False)

def mean_iou(model, dataloader) : 
    gpu1 = 'cuda:0'
    ious = list()
    for i, (data, target) in enumerate(dataloader) : 
        data, target = data.float().to(gpu1), target.long().to(gpu1)
        prediction = model(data)
        prediction = F.softmax(prediction, dim = 1)
        prediction = torch.argmax(prediction, axis = 1).squeeze(1)
        ious.append(iou(target, prediction, num_classes = 11))
        
    return (sum(ious) / len(ious))

for model_name in ['resnet10', 'resnet14', 'resnet18', 'resnet20', 'resnet26'] : 
    train_ious = list()
    val_ious = list()
    test_ious = list()
    unet = models.unet.Unet(model_name, classes = 12, encoder_weights = None).cuda()
    unet.load_state_dict(torch.load('../saved_models/camvid/trad_kd_new/' + model_name + '/classifier/model0.pt'))
    current_val_iou = mean_iou(unet, valloader)
    current_train_iou = mean_iou(unet, trainloader)
    current_test_iou = mean_iou(unet, testloader)
    train_ious.append(current_train_iou)
    val_ious.append(current_val_iou)
    test_ious.append(current_test_iou)
    print(round(current_train_iou, 5), round(current_val_iou, 5), round(current_test_iou, 5))