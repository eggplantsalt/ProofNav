"""Strictly load the frozen DUET checkpoint into the dynamic-fusion model."""

import argparse
import json

import torch

from models.model import VLNBert, Critic


def normalize_module_prefix(state_dict, model_state_dict):
    checkpoint_keys = list(state_dict)
    model_keys = list(model_state_dict)
    if checkpoint_keys and model_keys:
        checkpoint_module = checkpoint_keys[0].startswith("module.")
        model_module = model_keys[0].startswith("module.")
        if checkpoint_module and not model_module:
            return {key[7:]: value for key, value in state_dict.items()}
        if model_module and not checkpoint_module:
            return {"module." + key: value for key, value in state_dict.items()}
    return state_dict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    model_args = argparse.Namespace(
        bert_ckpt_file=None,
        tokenizer="bert",
        image_feat_size=768,
        angle_feat_size=4,
        obj_feat_size=768,
        num_l_layers=9,
        num_pano_layers=2,
        num_x_layers=4,
        graph_sprels=True,
        fusion="dynamic",
        fix_lang_embedding=False,
        fix_pano_embedding=False,
        fix_local_branch=False,
        feat_dropout=0.4,
        dropout=0.5,
    )
    models = {"vln_bert": VLNBert(model_args), "critic": Critic(model_args)}
    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    report = {"audit_type": "m0.checkpoint_strict_load.v1", "components": {}}
    for name, model in models.items():
        state_dict = normalize_module_prefix(
            checkpoint[name]["state_dict"], model.state_dict()
        )
        model.load_state_dict(state_dict, strict=True)
        report["components"][name] = {
            "strict_load": True,
            "parameter_tensor_count": len(state_dict),
        }
    report["passed"] = True
    with open(args.output, "w") as outfile:
        json.dump(report, outfile, sort_keys=True, indent=2)
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
