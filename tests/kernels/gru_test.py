# **************************************************
# Copyright (c) 2025, Mayank Mishra
# **************************************************

from typing import Callable

import torch
from parameterized import parameterized

from cute_kernels import GRU, KernelBackend, divide_if_divisible, gru_cute, set_seed

from ..test_commons import TestCommons


_SEED = 42


class GRUTest(TestCommons):
    @parameterized.expand(
        TestCommons.make_args_matrix(
            [torch.device("cuda")],
            TestCommons.get_dtypes(),
            [4],  # batch_size
            [1024],  # sequence_length
            [256],  # state_size
            [4, 256],  # num_heads
            [False, True],  # has_input_state
            [gru_cute, torch.compile(gru_cute, fullgraph=True)],  # function
        )
    )
    def test_gru(
        self,
        device: torch.device,
        dtype: torch.dtype,
        batch_size: int,
        sequence_length: int,
        state_size: int,
        num_heads: int,
        has_input_state: bool,
        function: Callable,
    ) -> None:
        set_seed(_SEED)

        (
            input_kernel,
            input_expected,
            weight_kernel,
            weight_expected,
            forget_input_kernel,
            forget_input_expected,
            forget_weight_kernel,
            forget_weight_expected,
            reset_input_kernel,
            reset_input_expected,
            reset_weight_kernel,
            reset_weight_expected,
            input_state_kernel,
            input_state_expected,
        ) = self._get_packed_tensor_inputs(
            batch_size=batch_size,
            sequence_length=sequence_length,
            total_tokens=None,
            num_heads=num_heads,
            state_size=state_size,
            has_input_state=has_input_state,
            dtype=dtype,
            device=device,
        )

        y_kernel = function(
            input=input_kernel,
            weight=weight_kernel,
            forget_input=forget_input_kernel,
            forget_weight=forget_weight_kernel,
            reset_input=reset_input_kernel,
            reset_weight=reset_weight_kernel,
            input_state=input_state_kernel,
        )

        y_expected = gru_cute(
            input=input_expected,
            weight=weight_expected,
            forget_input=forget_input_expected,
            forget_weight=forget_weight_expected,
            reset_input=reset_input_expected,
            reset_weight=reset_weight_expected,
            input_state=input_state_expected,
            kernel_backend=KernelBackend.torch,
        )

        y_kernel.sum().backward()
        y_expected.sum().backward()

        self.assert_equal_tensors(
            y_kernel,
            y_expected,
            False,
            atol_float32=4e-6,
            rtol_float32=0,
            atol_float16=6.5e-5,
            rtol_float16=0,
            atol_bfloat16=2e-4,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            input_kernel.grad,
            input_expected.grad,
            False,
            atol_float32=1.3e-4,
            rtol_float32=0,
            atol_float16=3e-3,
            rtol_float16=0,
            atol_bfloat16=1.6e-2,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            forget_input_kernel.grad,
            forget_input_expected.grad,
            False,
            atol_float32=2.5e-6,
            rtol_float32=0,
            atol_float16=5.4e-5,
            rtol_float16=0,
            atol_bfloat16=4e-4,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            reset_input_kernel.grad,
            reset_input_expected.grad,
            False,
            atol_float32=1.3e-6,
            rtol_float32=0,
            atol_float16=2e-6,
            rtol_float16=0,
            atol_bfloat16=1.2e-5,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            weight_kernel.grad,
            weight_expected.grad,
            False,
            atol_float32=1e-3,
            rtol_float32=1e-3,
            atol_float16=1.3e-2,
            rtol_float16=0,
            atol_bfloat16=7.5e-2,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            forget_weight_kernel.grad,
            forget_weight_expected.grad,
            False,
            atol_float32=6.3e-5,
            rtol_float32=0,
            atol_float16=1e-3,
            rtol_float16=0,
            atol_bfloat16=1.6e-2,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            reset_weight_kernel.grad,
            reset_weight_expected.grad,
            False,
            atol_float32=1.41e-5,
            rtol_float32=1e-10,
            atol_float16=8.4e-5,
            rtol_float16=0,
            atol_bfloat16=2.8e-3,
            rtol_bfloat16=0,
        )

    @parameterized.expand(
        TestCommons.make_args_matrix(
            [torch.device("cuda")],
            TestCommons.get_dtypes(),
            [[0, 7, 19, 27, 93]],  # cu_seqlens
            [256],  # state_size
            [4],  # num_heads
            [False, True],  # has_input_state
        )
    )
    def test_gru_varlen_torch(
        self,
        device: torch.device,
        dtype: torch.dtype,
        cu_seqlens: list[int],
        state_size: int,
        num_heads: int,
        has_input_state: bool,
    ) -> None:
        set_seed(_SEED)

        batch_size = len(cu_seqlens) - 1
        cu_seqlens = torch.tensor(cu_seqlens, device=device)
        max_seqlen = (cu_seqlens[1:] - cu_seqlens[:-1]).max()

        (
            input_packed_kernel,
            input_packed_expected,
            weight_kernel,
            weight_expected,
            forget_input_packed_kernel,
            forget_input_packed_expected,
            forget_weight_kernel,
            forget_weight_expected,
            reset_input_packed_kernel,
            reset_input_packed_expected,
            reset_weight_kernel,
            reset_weight_expected,
            input_state_kernel,
            input_state_expected,
        ) = self._get_packed_tensor_inputs(
            batch_size=batch_size,
            sequence_length=None,
            total_tokens=cu_seqlens[-1],
            num_heads=num_heads,
            state_size=state_size,
            has_input_state=has_input_state,
            dtype=dtype,
            device=device,
        )

        y_kernel = gru_cute(
            input=input_packed_kernel,
            weight=weight_kernel,
            forget_input=forget_input_packed_kernel,
            forget_weight=forget_weight_kernel,
            reset_input=reset_input_packed_kernel,
            reset_weight=reset_weight_kernel,
            input_state=input_state_kernel,
            cu_seqlens=cu_seqlens,
            max_seqlen=max_seqlen,
            kernel_backend=KernelBackend.torch,
        )

        y_expected = []
        for i in range(batch_size):
            y = gru_cute(
                input=input_packed_expected[cu_seqlens[i] : cu_seqlens[i + 1]].unsqueeze(0),
                weight=weight_expected,
                forget_input=forget_input_packed_expected[cu_seqlens[i] : cu_seqlens[i + 1]].unsqueeze(0),
                forget_weight=forget_weight_expected,
                reset_input=reset_input_packed_expected[cu_seqlens[i] : cu_seqlens[i + 1]].unsqueeze(0),
                reset_weight=reset_weight_expected,
                input_state=input_state_expected[i].unsqueeze(0) if has_input_state else None,
                kernel_backend=KernelBackend.torch,
            ).squeeze(0)
            y_expected.append(y)
        y_expected = torch.cat(y_expected)

        y_kernel.sum().backward()
        y_expected.sum().backward()

        self.assert_equal_tensors(y_kernel, y_expected, False)

        self.assert_equal_tensors(input_packed_kernel.grad, input_packed_expected.grad, False)
        self.assert_equal_tensors(forget_input_packed_kernel.grad, forget_input_packed_expected.grad, False)
        self.assert_equal_tensors(reset_input_packed_kernel.grad, reset_input_packed_expected.grad, False)

        self.assert_equal_tensors(
            weight_kernel.grad,
            weight_expected.grad,
            False,
            atol_float32=1.5e-7,
            rtol_float32=0,
            atol_float16=1.5e-3,
            rtol_float16=0,
            atol_bfloat16=6e-3,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            forget_weight_kernel.grad,
            forget_weight_expected.grad,
            False,
            atol_float32=1.5e-7,
            rtol_float32=0,
            atol_float16=1.5e-3,
            rtol_float16=0,
            atol_bfloat16=6e-3,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            reset_weight_kernel.grad,
            reset_weight_expected.grad,
            False,
            atol_float32=1.5e-7,
            rtol_float32=0,
            atol_float16=1.5e-3,
            rtol_float16=0,
            atol_bfloat16=6e-3,
            rtol_bfloat16=0,
        )

    @parameterized.expand(
        TestCommons.make_args_matrix(
            [torch.device("cuda")],
            TestCommons.get_dtypes(),
            [[0, 7, 19, 27, 93]],  # cu_seqlens
            [256],  # state_size
            [4],  # num_heads
            [False, True],  # has_input_state
        )
    )
    def test_gru_varlen_cute(
        self,
        device: torch.device,
        dtype: torch.dtype,
        cu_seqlens: list[int],
        state_size: int,
        num_heads: int,
        has_input_state: bool,
    ) -> None:
        set_seed(_SEED)

        batch_size = len(cu_seqlens) - 1
        cu_seqlens = torch.tensor(cu_seqlens, device=device)
        max_seqlen = (cu_seqlens[1:] - cu_seqlens[:-1]).max()

        (
            input_kernel,
            input_expected,
            weight_kernel,
            weight_expected,
            forget_input_kernel,
            forget_input_expected,
            forget_weight_kernel,
            forget_weight_expected,
            reset_input_kernel,
            reset_input_expected,
            reset_weight_kernel,
            reset_weight_expected,
            input_state_kernel,
            input_state_expected,
        ) = self._get_packed_tensor_inputs(
            batch_size=batch_size,
            sequence_length=None,
            total_tokens=cu_seqlens[-1],
            num_heads=num_heads,
            state_size=state_size,
            has_input_state=has_input_state,
            dtype=dtype,
            device=device,
        )

        y_kernel = gru_cute(
            input=input_kernel,
            weight=weight_kernel,
            forget_input=forget_input_kernel,
            forget_weight=forget_weight_kernel,
            reset_input=reset_input_kernel,
            reset_weight=reset_weight_kernel,
            input_state=input_state_kernel,
            cu_seqlens=cu_seqlens,
            max_seqlen=max_seqlen,
        )

        y_expected = gru_cute(
            input=input_expected,
            weight=weight_expected,
            forget_input=forget_input_expected,
            forget_weight=forget_weight_expected,
            reset_input=reset_input_expected,
            reset_weight=reset_weight_expected,
            input_state=input_state_expected,
            cu_seqlens=cu_seqlens,
            max_seqlen=max_seqlen,
            kernel_backend=KernelBackend.torch,
        )

        y_kernel.sum().backward()
        y_expected.sum().backward()

        self.assert_equal_tensors(
            y_kernel,
            y_expected,
            False,
            atol_float32=3e-6,
            rtol_float32=0,
            atol_float16=6.5e-5,
            rtol_float16=0,
            atol_bfloat16=1.5e-4,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            input_kernel.grad,
            input_expected.grad,
            False,
            atol_float32=1.3e-4,
            rtol_float32=0,
            atol_float16=3e-3,
            rtol_float16=0,
            atol_bfloat16=8e-3,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            forget_input_kernel.grad,
            forget_input_expected.grad,
            False,
            atol_float32=2e-6,
            rtol_float32=0,
            atol_float16=3.1e-5,
            rtol_float16=0,
            atol_bfloat16=2e-4,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            reset_input_kernel.grad,
            reset_input_expected.grad,
            False,
            atol_float32=1.1e-6,
            rtol_float32=0,
            atol_float16=1.5e-5,
            rtol_float16=0,
            atol_bfloat16=1.6e-5,
            rtol_bfloat16=0,
        )

        self.assert_equal_tensors(
            weight_kernel.grad,
            weight_expected.grad,
            False,
            atol_float32=1.6e-4,
            rtol_float32=0,
            atol_float16=3.7e-4,
            rtol_float16=0,
            atol_bfloat16=2.5e-3,
            rtol_bfloat16=0,
        )

        print((forget_weight_kernel.grad - forget_weight_expected.grad).abs().max().item(), input_kernel.grad.dtype)

        self.assert_equal_tensors(
            forget_weight_kernel.grad,
            forget_weight_expected.grad,
            False,
            atol_float32=2.7e-6,
            rtol_float32=0,
            atol_float16=3.9e-6,
            rtol_float16=0,
            atol_bfloat16=3.1e-5,
            rtol_bfloat16=0,
        )

        print((reset_weight_kernel.grad - reset_weight_expected.grad).abs().max().item(), input_kernel.grad.dtype)

        self.assert_equal_tensors(
            reset_weight_kernel.grad,
            reset_weight_expected.grad,
            False,
            atol_float32=2.3e-6,
            rtol_float32=0,
            atol_float16=3.9e-6,
            rtol_float16=0,
        )

    @parameterized.expand(
        TestCommons.make_args_matrix(
            [torch.device("cuda")],
            TestCommons.get_dtypes(),
            [[0, 7, 19, 27, 93], None],  # cu_seqlens
            [256],  # state_size
            [4],  # num_heads
        )
    )
    def test_gru_module(
        self,
        device: torch.device,
        dtype: torch.dtype,
        cu_seqlens: list[int] | None,
        state_size: int,
        num_heads: int,
    ) -> None:
        input_size = 79
        output_size = 93

        gru = GRU(
            input_size=input_size,
            state_size=state_size,
            output_size=output_size,
            num_heads=num_heads,
            add_bias=False,
            gradient_clipping=None,
        ).to(device, dtype)

        batch_size = 4 if cu_seqlens is None else len(cu_seqlens) - 1
        cu_seqlens = None if cu_seqlens is None else torch.tensor(cu_seqlens, device=device)
        max_seqlen = None if cu_seqlens is None else (cu_seqlens[1:] - cu_seqlens[:-1]).max()

        input = (
            torch.randn(batch_size, 1024, input_size, device=device, dtype=dtype)
            if cu_seqlens is None
            else torch.randn(cu_seqlens[-1], input_size, device=device, dtype=dtype)
        )
        input_state = torch.randn(batch_size, state_size, device=device, dtype=dtype)

        output, output_state = gru(
            input=input, input_state=input_state, cu_seqlens=cu_seqlens, max_seqlen=max_seqlen, use_kernel=True
        )

        output.sum().backward()

        assert output.size() == (*input.size()[:-1], output_size)
        assert output_state.size() == input_state.size()

    def _get_packed_tensor_inputs(
        self,
        batch_size: int,
        sequence_length: int | None,
        total_tokens: int | None,
        num_heads: int,
        state_size: int,
        has_input_state: bool,
        dtype: torch.dtype,
        device: torch.device,
    ) -> tuple[torch.Tensor | None]:
        head_dim = divide_if_divisible(state_size, num_heads)

        input_kernel, input_expected = self.get_random_duplicated_tensors(
            (
                (batch_size, sequence_length, num_heads, head_dim)
                if total_tokens is None
                else (total_tokens, num_heads, head_dim)
            ),
            device=device,
            dtype=dtype,
            std=0.01,
        )

        weight_kernel, weight_expected = self.get_random_duplicated_tensors(
            (num_heads, head_dim, head_dim), device=device, dtype=dtype, std=0.01
        )

        # forget
        forget_input_kernel, forget_input_expected = self.get_random_duplicated_tensors(
            (
                (batch_size, sequence_length, num_heads, head_dim)
                if total_tokens is None
                else (total_tokens, num_heads, head_dim)
            ),
            device=device,
            dtype=dtype,
            std=0.01,
        )

        forget_weight_kernel, forget_weight_expected = self.get_random_duplicated_tensors(
            (num_heads, head_dim, head_dim), device=device, dtype=dtype, std=0.01
        )

        # reset
        reset_input_kernel, reset_input_expected = self.get_random_duplicated_tensors(
            (
                (batch_size, sequence_length, num_heads, head_dim)
                if total_tokens is None
                else (total_tokens, num_heads, head_dim)
            ),
            device=device,
            dtype=dtype,
            std=0.01,
        )

        reset_weight_kernel, reset_weight_expected = self.get_random_duplicated_tensors(
            (num_heads, head_dim, head_dim), device=device, dtype=dtype, std=0.01
        )

        input_state_kernel = None
        input_state_expected = None
        if has_input_state:
            input_state_kernel, input_state_expected = self.get_random_duplicated_tensors(
                (batch_size, num_heads, head_dim), device=device, dtype=dtype, std=0.01
            )

        return (
            input_kernel,
            input_expected,
            weight_kernel,
            weight_expected,
            forget_input_kernel,
            forget_input_expected,
            forget_weight_kernel,
            forget_weight_expected,
            reset_input_kernel,
            reset_input_expected,
            reset_weight_kernel,
            reset_weight_expected,
            input_state_kernel,
            input_state_expected,
        )
