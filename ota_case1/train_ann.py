import torch
import os
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
from initial_ann import ANN,dataloader

PWD = os.getcwd()

model = ANN()
# 定义损失函数和优化器
criterion = nn.MSELoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# 用于保存训练损失的列表
train_losses = []

# 训练模型
epochs = 2000
for epoch in range(epochs):
    epoch_loss = 0  # 每个epoch的总损失
    for batch_X, batch_Y in dataloader:
        optimizer.zero_grad()
        output = model(batch_X)
        loss = criterion(output, batch_Y)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item()  # 累加当前batch的损失

    # 计算平均损失
    avg_loss = epoch_loss / len(dataloader)
    train_losses.append(avg_loss)  # 保存每个epoch的平均损失

    # 每10个epoch打印一次
    if (epoch + 1) % 10 == 0:
        print(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.6f}")

# 保存模型
torch.save(model.state_dict(), f"{PWD}/op_pth/case1_model_ea_op.pth")
print("模型训练完成并保存！")

# 绘制训练曲线
plt.plot(range(1, epochs + 1), train_losses, label="Training Loss")
plt.xlabel("Epochs")
plt.ylabel("Loss")
plt.title("Training Loss Curve_case1_op")
plt.legend()
plt.savefig(f"{PWD}/op_pth/training_loss_curve_case1_op.png")  # 保存训练曲线
plt.show()
