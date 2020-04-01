from comet_ml import Experiment
import torch
import torch.nn as nn
from torchvision import transforms
from torch.utils.data import DataLoader
import torch.nn.functional as F
import models
import argparse
from helper import *
torch.cuda.set_device(0)

parser = argparse.ArgumentParser(description = 'Stagewise training of UNet based on ResNet encoder')
parser.add_argument('-m', choices = ['resnet10', 'resnet14', 'resnet18', 'resnet20', 'resnet26'], help = 'Give the encoder name from the choices')
parser.add_argument('-e', type = int, help = 'Give number of epochs for training')
parser.add_argument('-s', type = int, help = 'Give the random seed number')
args = parser.parse_args()

torch.manual_seed(args.s)
torch.cuda.manual_seed(args.s)

classes = ['sky', 'building', 'pole', 'road', 'pavement', 'tree', 'signsymbol', 'fence', 'car', 'pedestrian', 'bicyclist', 'unlabelled']
DATA_DIR = '../data/CamVid/'
x_train_dir = os.path.join(DATA_DIR, 'train')
y_train_dir = os.path.join(DATA_DIR, 'trainannot')

x_valid_dir = os.path.join(DATA_DIR, 'val')
y_valid_dir = os.path.join(DATA_DIR, 'valannot')

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

hyper_params = {
        "model": args.m,
        "seed": args.s,
        "num_classes": 12,
        "batch_size": 8,
        "num_epochs": args.e,
        "learning_rate": 1e-4,
}

trainloader = DataLoader(train_dataset, batch_size = hyper_params['batch_size'], shuffle = True, drop_last = True)
valloader = DataLoader(valid_dataset, batch_size = 1, shuffle = False)

student = models.unet.Unet(hyper_params['model'], classes = 12, encoder_weights = None).cuda()
teacher = models.unet.Unet('resnet34', classes = 12, encoder_weights = None).cuda()
teacher.load_state_dict(torch.load('../saved_models/camvid/resnet34/pretrained_0.pt'))
# Freeze the teacher model
teacher = unfreeze(teacher, 30)

sf_student = [SaveFeatures(m) for m in [student.encoder.layer2, 
                                        student.decoder.blocks[2], 
                                        ]]

sf_teacher = [SaveFeatures(m) for m in [teacher.encoder.layer2, 
                                        teacher.decoder.blocks[2], 
                                        ]]

# project_name = 'trad-kd-camvid-' + hyper_params['model']
# experiment = Experiment(api_key="1jNZ1sunRoAoI2TyremCNnYLO", project_name = project_name, workspace="semseg_kd")
# experiment.log_parameters(hyper_params)

# optimizer = torch.optim.Adam(student.parameters(), lr = hyper_params['learning_rate'])
# scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr = 1e-2, steps_per_epoch = len(trainloader), epochs = hyper_params['num_epochs'])
# criterion = nn.CrossEntropyLoss(ignore_index = 11)
# criterion2 = nn.MSELoss()

# savename = '../saved_models/camvid/trad_kd/' + hyper_params['model'] + '/model' + str(hyper_params['seed']) + '.pt'
# highest_iou = 0
# losses = []
# for epoch in range(hyper_params['num_epochs']) :
#     student, highest_iou, train_loss, val_loss, avg_iou, avg_pixel_acc, avg_dice_coeff = train_trad_kd(model = student, 
#                         teacher = teacher,
#                         sf_teacher = sf_teacher,
#                         sf_student = sf_student,
#                         train_loader = trainloader, 
#                         val_loader = valloader,
#                         num_classes = 12,
#                         loss_function1 = criterion,
#                         loss_function2 = criterion2, 
#                         optimiser = optimizer, 
#                         scheduler = scheduler, 
#                         epoch = epoch, 
#                         num_epochs = hyper_params['num_epochs'], 
#                         savename = savename, 
#                         highest_iou = highest_iou
#                        )
#     experiment.log_metric('train_loss', train_loss)
#     experiment.log_metric('val_loss', val_loss)
#     experiment.log_metric('avg_iou', avg_iou)
#     experiment.log_metric('avg_pixel_acc', avg_pixel_acc)
#     experiment.log_metric('avg_dice_coeff', avg_dice_coeff)

for stage in range(2) : 
    # update hyperparams dictionary
    hyper_params['stage'] = stage

    # Load previous stage model (except zeroth stage)
    if stage != 0 : 
        savename = '../saved_models/camvid/trad_kd_new/' + hyper_params['model'] + '/stage' + str(hyper_params['stage'] - 1) + '/model' + str(hyper_params['seed']) + '.pt'
        student.load_state_dict(torch.load(savename))
        
    # Freeze all stages except current stage
    student = unfreeze_trad(student, hyper_params['stage'])
    
    project_name = 'new-trad-kd-' + hyper_params['model']
    experiment = Experiment(api_key="1jNZ1sunRoAoI2TyremCNnYLO", project_name = project_name, workspace="semseg_kd")
    experiment.log_parameters(hyper_params)
    
    optimizer = torch.optim.Adam(student.parameters(), lr = hyper_params['learning_rate'])
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr = 1e-2, steps_per_epoch = len(trainloader), epochs = hyper_params['num_epochs'])
    criterion = nn.MSELoss()
    
    savename = '../saved_models/camvid/trad_kd_new/' + hyper_params['model'] + '/stage' + str(hyper_params['stage']) + '/model' + str(hyper_params['seed']) + '.pt'
    lowest_val_loss = 100
    losses = []
    for epoch in range(hyper_params['num_epochs']) :
        student, lowest_val_loss, train_loss, val_loss = train_stage(model = student,
                            teacher = teacher,
                            stage = hyper_params['stage'],
                            sf_student = sf_student, 
                            sf_teacher = sf_teacher,
                            train_loader = trainloader, 
                            val_loader = valloader,
                            loss_function = criterion, 
                            optimiser = optimizer, 
                            scheduler = scheduler, 
                            epoch = epoch, 
                            num_epochs = hyper_params['num_epochs'], 
                            savename = savename, 
                            lowest_val = lowest_val_loss
                           )
        experiment.log_metric('train_loss', train_loss)
        experiment.log_metric('val_loss', val_loss)

# Classifier training
hyper_params['stage'] = 2
savename = '../saved_models/camvid/trad_kd_new/' + hyper_params['model'] + '/stage' + str(hyper_params['stage'] - 1) + '/model' + str(hyper_params['seed']) + '.pt'
student.load_state_dict(torch.load(savename))

# Freeze all stages except current stage
student = unfreeze_trad(student, hyper_params['stage'])

project_name = 'new-trad-kd-' + hyper_params['model']
experiment = Experiment(api_key="1jNZ1sunRoAoI2TyremCNnYLO", project_name = project_name, workspace="semseg_kd")
experiment.log_parameters(hyper_params)

optimizer = torch.optim.Adam(student.parameters(), lr = hyper_params['learning_rate'])
scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr = 1e-2, steps_per_epoch = len(trainloader), epochs = hyper_params['num_epochs'])
criterion = nn.CrossEntropyLoss(ignore_index = 11)

savename = '../saved_models/camvid/trad_kd_new/' + hyper_params['model'] + '/classifier/model' + str(hyper_params['seed']) + '.pt'
highest_iou = 0
losses = []
for epoch in range(hyper_params['num_epochs']) :
    student, highest_iou, train_loss, val_loss, avg_iou, avg_pixel_acc, avg_dice_coeff = train(model = student, 
                        train_loader = trainloader, 
                        val_loader = valloader,
                        num_classes = 12,
                        loss_function = criterion, 
                        optimiser = optimizer, 
                        scheduler = scheduler, 
                        epoch = epoch, 
                        num_epochs = hyper_params['num_epochs'], 
                        savename = savename, 
                        highest_iou = highest_iou
                       )
    experiment.log_metric('train_loss', train_loss)
    experiment.log_metric('val_loss', val_loss)
    experiment.log_metric('avg_iou', avg_iou)
    experiment.log_metric('avg_pixel_acc', avg_pixel_acc)
    experiment.log_metric('avg_dice_coeff', avg_dice_coeff)