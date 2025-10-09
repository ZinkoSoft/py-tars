#!/usr/bin/env python3
"""Inspect ONNX model structure to understand input/output shapes."""

import sys
from pathlib import Path
import onnx

def inspect_onnx_model(model_path: Path):
    """Inspect ONNX model structure."""
    print(f"Inspecting ONNX model: {model_path}")
    
    try:
        model = onnx.load(str(model_path))
        
        print("\n=== Model Info ===")
        print(f"Producer: {model.producer_name}")
        print(f"Version: {model.producer_version}")
        print(f"Graph name: {model.graph.name}")
        
        print("\n=== Inputs ===")
        for i, input_tensor in enumerate(model.graph.input):
            print(f"Input {i}: {input_tensor.name}")
            print(f"  Type: {input_tensor.type.tensor_type.elem_type}")
            
            shape = []
            for dim in input_tensor.type.tensor_type.shape.dim:
                if dim.dim_value:
                    shape.append(dim.dim_value)
                elif dim.dim_param:
                    shape.append(dim.dim_param)
                else:
                    shape.append("?")
            print(f"  Shape: {shape}")
        
        print("\n=== Outputs ===")
        for i, output_tensor in enumerate(model.graph.output):
            print(f"Output {i}: {output_tensor.name}")
            print(f"  Type: {output_tensor.type.tensor_type.elem_type}")
            
            shape = []
            for dim in output_tensor.type.tensor_type.shape.dim:
                if dim.dim_value:
                    shape.append(dim.dim_value)
                elif dim.dim_param:
                    shape.append(dim.dim_param)
                else:
                    shape.append("?")
            print(f"  Shape: {shape}")
        
        print("\n=== Graph Nodes (first 10) ===")
        for i, node in enumerate(model.graph.node[:10]):
            print(f"Node {i}: {node.op_type}")
            print(f"  Inputs: {list(node.input)}")
            print(f"  Outputs: {list(node.output)}")
        
        if len(model.graph.node) > 10:
            print(f"... and {len(model.graph.node) - 10} more nodes")
            
    except Exception as e:
        print(f"Error inspecting model: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python inspect_onnx.py <model.onnx>")
        sys.exit(1)
    
    model_path = Path(sys.argv[1])
    if not model_path.exists():
        print(f"Model file not found: {model_path}")
        sys.exit(1)
    
    inspect_onnx_model(model_path)