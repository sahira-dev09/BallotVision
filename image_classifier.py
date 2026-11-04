import torch
from PIL import Image
from torchvision.models import mobilenet_v2, MobileNet_V2_Weights


class ImageClassifier:
    def __init__(self):
        self.weights = MobileNet_V2_Weights.DEFAULT
        self.model = mobilenet_v2(weights=self.weights)
        self.model.eval()

        self.preprocess = self.weights.transforms()
        self.categories = self.weights.meta["categories"]

    def classify(self, image_path, top_k=5):
        image = Image.open(image_path).convert("RGB")

        input_tensor = self.preprocess(image)
        input_batch = input_tensor.unsqueeze(0)

        with torch.no_grad():
            output = self.model(input_batch)

        probabilities = torch.nn.functional.softmax(
            output[0],
            dim=0
        )

        top_probabilities, top_indices = torch.topk(
            probabilities,
            top_k
        )

        results = []

        for probability, index in zip(
            top_probabilities,
            top_indices
        ):
            results.append({
                "label": self.categories[index],
                "confidence": probability.item() * 100,
            })

        return results