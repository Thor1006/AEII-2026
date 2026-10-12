import torch
import torch.nn as nn

if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")
print(f"using device: {device}")

Model_layer = int(input("INPUT AMOUNT OF HIDDEN LAYER HERE: "))
Model_size = int(input("INPUT AMOUNT OF NEURON PER HIDDEN LAYER HERE:"))


X = torch.linspace(-5, 5, 100, device=device).unsqueeze(1)
Y = X ** 3 + 5

def memory_usage():
    if device.type == "mps":
        return torch.mps.current_allocated_memory() / 1e9
    if device.type == "cuda":
        return torch.cuda.memory_allocated() / 1e9
    return 0.0

import torch.nn as nn

def make_model(
    input_size,
    hidden_size,
    hidden_layers,
    output_size,
    device
):
    layers = []

    layers.append(nn.Linear(input_size, hidden_size))
    layers.append(nn.LeakyReLU())

    for _ in range(hidden_layers - 1):
        layers.append(nn.Linear(hidden_size, hidden_size))
        layers.append(nn.LeakyReLU())

    layers.append(nn.Linear(hidden_size, output_size))

    return nn.Sequential(*layers).to(device)

make_model(
    1,
    Model_size,
    Model_layer,
    1,
    device
)

total_params = sum(p.numel() for p in make_model.paramerters)
print(f"Total parameters: {total_params:,}")
print(f"Memory allocated to model: {memory_usage():.2f}")

shoe_layer = False

loss_fn = nn.MSELoss()
optimizer = torch.optim.Adam(make_model.parameters(), lr=0.00001)

for epoch in range(3000):
    show_progress = epoch % 100 == 0
    if show_progress:
        print(f"Epoch: {epoch}")
    optimizer.zero_grad()
    loss = loss_fn(make_model(X), Y)
    optimizer.step()
    if show_progress:
        print(f"epoch {epoch}, loss {loss.item():.4f}, memory {memory_usage():.2f} GB")

print(f"final loss: {loss.item():.4f}")
print(f"memory at end of training: {memory_usage():.2f} GB")
with torch.no_grad():
    for value in [-2.5, -1.0, 0.0, 1.5, 2.0]:
            pred = make_model(torch.tensor([[value]], device=device)).item()
            print(f"x = {value:5.2f}, predicted = {pred:6.3f}, actual = {value ** 2 + 5:6.3f}")
    