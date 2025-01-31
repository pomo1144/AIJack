import torch

from ...utils.metrics import crossentropyloss_between_logits
from ...utils.utils import torch_round_x_decimal
from ..core import BaseClient


class DSFLClient(BaseClient):
    def __init__(
        self,
        model,
        public_dataloader,
        output_dim=1,
        round_decimal=None,
        device="cpu",
        user_id=0,
    ):
        super().__init__(model, user_id)
        self.public_dataloader = public_dataloader
        self.round_decimal = round_decimal
        self.device = device
        self.global_logit = None

        len_public_dataloader = len(self.public_dataloader.dataset)
        self.logit2server = torch.ones((len_public_dataloader, output_dim)).to(
            self.device
        ) * float("inf")

    def upload(self):
        for data in self.public_dataloader:
            idx = data[0]
            x = data[1]
            x = x.to(self.device)
            self.logit2server[idx, :] = self(x).detach()

        if self.round_decimal is None:
            return self.logit2server
        else:
            return torch_round_x_decimal(self.logit2server, self.round_decimal)

    def download(self, global_logit):
        self.global_logit = global_logit

    def approach_consensus(self, consensus_optimizer):
        running_loss = 0
        for global_data in self.public_dataloader:
            idx = global_data[0]
            x = global_data[1].to(self.device)
            y_global = self.global_logit[idx, :].to(self.device).detach()
            consensus_optimizer.zero_grad()
            y_local = self(x)
            loss_consensus = crossentropyloss_between_logits(y_local, y_global)
            loss_consensus.backward()
            consensus_optimizer.step()
            running_loss += loss_consensus.item()
        running_loss /= len(self.public_dataloader)
        return running_loss
