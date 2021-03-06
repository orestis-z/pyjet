![](https://raw.githubusercontent.com/wolfv/pyjet/master/docs/img/jet_logo.png)

JET - compiling NumPy
=====================

The JET library offers a simple way to make Python, and especially NumPy code
run faster. This is achieved by transparently converting Python/NumPy operations
to performant C++.

## Overview

The design of JET is inspired by TensorFlow and Theano, two machine learning
libraries that work on a computation graph. JET internally also creates a
computation graph and converts that to C++. This works by leveraging Pythons
operator overloading, instead of calculating something, adding the specific
operation to the computation graph.

The computation graph is represented as a Directed Acyclic Graph (DAG). Nodes of
the graph represent a specific operation and edges are the data that flows
between the nodes.

***

## Use Case

Significant speed-up is achieved for non-parallelizable functions such as
physical models. For parallelizable functions please consider using TensorFlow.

Instead of calling a huge, math-heavy Python/NumPy simulation model on every
iteration JET packs the whole model in a single performant C++ function which 
results in an enormous speed-up (up to 60-fold speed up was observed in a
simulation of a math-heavy quadcopter-model).

```python
from jet.jit import jit

import scipy.integrate
from simulation_model import state_derivatives, init_state, time_vec

jet_state_derivatives = jit(state_derivatives)

states = scipy.integrate.odeint(
    jet_state_derivatives,
    init_state,
    time_vec)
```

## Setup

Run the post-install script using the JET-cli:

    sudo jet --install-dependencies

Note: Is currently only tested on Ubuntu (known to be broken on macOS).

## Tutorial Style Introduction

JET gives you a few operators to use, modelled after TensorFlow.

The `jet.placeholder` is a operator that will later be an input to the generated
function. A `jet.variable` is a state that is attached to the JetClass you are
instantiating. It can be modified like a class member of a Python class. And the
last special variable is the `jet.constant`. A constant is, once compiled, not
modifiable anymore.

The following example will guide you through the main principles of JET.

```python
import jet as jt

ph  = jt.placeholder(name='holder', shape=(3, 3))
var   = jt.variable(name='variable', value=np.zeros((2, 1)))
const = jt.constant(name='constant', value=1.5)

op = ph[1, 1] + ph[0:2, 0:2] * var + const
out0 = jt.concatenate((var, op), axis=1)
out1 = jt.linalg.norm(var)
ph[0:2, 0:1] = var

from jet.burn import draw
draw(jt.graph)
```

This will create the following computation graph:

![](https://s31.postimg.org/53c78nf0r/graph.png)

The dotted grey edges ensure that their head is executed after their tail.

```python
from jet.compressor import JetBuilder
jb = JetBuilder(out=[out0, out1], fun_name='test', file_name='test_jet')
```

Starting at the out-nodes, `JetBuilder` traverses the graph backwards and
collects all nodes necessary to compute the output-values.

```python
test_source = jb.to_cpp()
print(test_source)  # this is the real C++ that got generated
```

This will output the following auto-generated C++ code:

```cpp
#include <cmath>
#include <tuple>
#include <vector>
#include <string>
#include <armadillo>
#include <iostream>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "armadillo.h"
#include "supportlib.h"

using namespace arma;
using namespace std;

// constants
constexpr double constant = 1.5;

class TestClass {
public:
  // member variables
  mat::fixed<2, 1> variable = {0.0, 0.0};

  tuple<mat::fixed<2, 3>, double>
  test(mat::fixed<3, 3> holder) {

    mat::fixed<2, 2> View = holder(span(0, 1), span(0, 1)).eval();
    double Norm = norm(variable);
    mat::fixed<2, 2> Add_0 =
        ((holder.eval()(1, 1)) + (View.eval().each_col() % variable))
        + constant;
    mat::fixed<2, 3> Concatenate = join_rows(variable, Add_0);

    return make_tuple(Concatenate, Norm);
  }
};

namespace py = pybind11;
void pyexport(py::module &m) { // Python glue
  py::class_<TestClass>(m, "TestClass")
      .def(py::init<>()) // initialisation
      .def("test", &TestClass::test) // Access to function
      .def("args", [](TestClass &) {
          return std::vector<std::string>{"holder"}; }) // String-vector containing the ordered argument names
      .def_readwrite("variable", &TestClass::variable); // Access to variable
}
```

We can compile the source code using `build` which returns
the compiled and imported Python module:

```python
test_module = jb.build()
test_class = test_module.TestClass()

# adjustable class member 'variable':
test_class.variable = np.array([1, 2])

# calling our function
print test_class.test(np.ones((3,3)))
```

This prints the following output-tuple:

```text
(array([[ 1. ,  3.5,  3.5],
        [ 2. ,  4.5,  4.5]]), 2.23606797749979)
```

Comparing with NumPy:

```python
import numpy as np # numpy to compare

ph = np.ones((3,3))
var = np.array([[1], [2]])
const = 1.5

op = ph[1, 1] + ph[0:2, 0:2] * var + const
out0 = np.concatenate((var, op), axis=1)
out1 = np.linalg.norm(var)
ph[0:2, 0:1] = var

print out0, out1
```

gives us the following output:

```text
[[ 1.   3.5  3.5]
 [ 2.   4.5  4.5]] 2.2360679775
```

***

### JIT-Decorator
The quickest way to speed up a function with JET is by using the JIT
(Just-In-Time compiler) decorator:

```python
from jet import jit
import numpy as np

@jit((2,), ()) # or @jit, @jit()
def calc(a, b):
    c = a + b
    return c

print(calc(np.array([1, 2]), 2))
```
The `@jit` decorator takes the function argument shapes as tuple parameters.
JET will detect the shapes by evaluating the input arguments if no shapes are 
passed to the decorator.

Supported shapes:
* scalar: `()`
* vector: `(n,)`
* matrix: `(n, m)`

***

### Migrating from a NumPy-project

When migrating from a NumPy project there are minor steps which must be taken:
* Replace NumPy operations with JET operations. Usually replacing `import numpy 
as np` with `import jet as np` is sufficient. You don't have to replace constants
such as `np.array([1, 2])` with JET-arrays.
* Decorate all top-level functions with the JIT-decorator (or manually pass
placeholders like in the tutorial above).


E.g.:

```python
import numpy as np

def sub_func(a):
    return a * 2

def func(a, b):
    c = sub_func(a) + b
    return np.dot(c, c)

print(func(np.array([1, 2]), 2))
```

becomes

```python
import jet as np
from jet.jit import jit

def sub_func(a):
    return a * 2

@jit
def func(a, b):
    c = sub_func(a) + b
    return np.dot(c, c)

import numpy
print(func(numpy.array([1, 2]), 2))
```

***

## Supported operations

Note: The biggest problem is that some control-flow operations are *not*
supported. For example, it is not possible to use `if - else` or `while` and
`for` statements. As workaround for `if - else` the NumPy command `where` is
currently provided.

`jet.array`: Base array class which emulates NumPy arrays. Variables, Constants
and Placeholders are derived from this class.

### Member attributes of `array` class:

`array.name`: Unique name of the array.

`array.dtype`: Data type of the array.

`array.shape`: Shape of the array.

`array.ndim`: Number of dimensions of the array (equivalent to `len(array.shape)`).

`array.producer`: Returns a JET-specific operation-object which produced the
array.

### Member functions of `array` class:

`array.transpose()` or `array.T`: Transpose the array.

`array.copy()`: Create a copy of the array.

`array.ravel()`: Convert array to one dimensional representation.

`array.reshape()`: Reshape array.

`+`, `-`, `*`, `/`, `**`, `+=`,`-=`, `*=`, `/=`, `**=`, `==`, `!=`, `<`, `<=`,
`>`, `>=`: Overloaded Python operators.

### `array` views and slices:
Elements of an array can be set using the usual NumPy assignment operations,
such as:

```python
a = jt.array([[1,2,3], [4,5,6]])
a[0, 0] = 100 # call of __setitem__
a[:, 1] = np.array([10, 20])
```

In the same spirit, the array can be sliced for operations:

```python
b = np.array([1,2,3])
c = b + a[0, :] # call of __getitem__
```

However, one important distinction is that array slicing does not create views
as flexible as NumPys. The following will not change `a` as it would in Python.

```python
v = a[0, :]
v[0] = 100
```

Also, slices with steps or negative values are currently not supported (e.g. `1:3:-2`).

### Built-in functions:

`abs(array)`: Elementwise absolute value operation.

`len(array)`: Returns the length of the first dimension (equivalent to
`array.shape[0]`)

### JET constans:

All NumPy constants such as `pi` and `inf` are supported.

### JET functions:

`add`, `subtract`, `multiply`, `divide`, `power(x, y)`: Elementary binary operations.

`negative`, `reciprocal(x)`: Elementary unary operations.

`fabs`, `sqrt`, `square`, `exp`, `log(x)`: Elementwise unary operations.

`sin`, `cos`, `tan`, `arcsin`, `arccos`, `arctan(x)`: Elementwise trigonometry operations.

`mod`, `atan2(x, y)`: Elementwise binary operations.

`maximum`, `minimum(x, y)`: Extract maximum/minimum (does not work elementwise
currently).

`sign(x)`: Extract sign of x (does not work elementwise
currently).

`matmul`, `dot`, `cross(x, y)`: Vector and matrix operations.

`eye(n)`: Creation of a nxn identity matrix.

`zeros`, `ones(size)`: Creation of matrices with specified fill value (size can be
a shape-tuple or vector-length-integer).

`clip(val, min, max)`: Clip value elementwise between `min` and `max`.

`where(cond, x, y)`: Return `x` or `y` depending on the evaluation of
                          `cond`. If `True`, return `x`, otherwise `y`.

`concatenate((x1, x2, ...), axis=0)`: Concatenate values along axis.

`vstack((x1, x2, ...))`: Identical to `concatenate(tup, axis=0)`.

`hstack((x1, x2, ...))`: Identical to `concatenate(tup, axis=1)`.

`logical_and`, `logical_or`, `logical_xor(x, y)`: Logical operator functions.

`logical_not(x)`: Logical not function.

### `linalg` class:

`linalg.solve(lhs, rhs)`: Solve linear System `lhs * x = rhs` for `x`.

`linalg.norm(x, order=2)`: Return norm of vector `x`. Only vector and 2nd order
norm supported currently.

### `random` class:

`random.normal(mean=0, sd=1)`: Draw random samples from a normal (Gaussian)
distribution. `mean` and `sd` can be vectors.

***

## Set JET Options

We can specify with which mode JET is flying when running a script which imports
JET using the `set_options` function:

```python
jet.set_options(jet_mode=True,
                debug=False,
                no_merge=False,
                draw_graph=False,
                draw_graph_raw=False,
                group_class=False,
                group_func=False,
                DTYPE=numpy.float64)
```

`jet_mode`:           Fly Mach 2 with JET. If this flag is not set JET will
                      run using NumPy instead.

`debug`:              Print what JET is doing. Every variable from the auto-
                      generated C++ code is printed in the console along
                      with an identifier from the auto-generated C++ code.

`no_merge`            If not set, JET will merge some operations such as
                      addition and multiplication into one execution statement
                      in the auto-generated C++ code.

`draw_graph`:         Draw the JET-graph. A dot graph of the JET-function is
                      stored in the 'jet-graph' folder.

`draw_graph_raw`:     Draw the raw jet-graph. A dot graph of the JET-
                      function is stored in the 'jet-graph' folder without
                      cleaning out the unused nodes.

`group_class`:        Group nodes from the same class in graph-drawing.

`group_func`:         Group nodes from the same function in the graph-
                      drawing.

`DTYPE`:              Basic float type such as `numpy.float32` or `numpy.float64`.

***

## JET-CLI

```text
usage: jet [-h] [-c] [--install-dependencies] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -c, --clean           delete all files generated by JET
  --install-dependencies
                        install JET dependencies
  -v, --version         show version number
```

***

## Dependencies

| Dependency      | Description |
| --------------- | :--------------------------------------------------------- |
| Armadillo       | Currently, Armadillo is used as library for matrix operations. It gets automatically installed when building the package with Catkin |
| CMake           | Tool required to build Armadillo |
| BLAS and LAPACK | Linear algebra libraries required by Armadillo |
| PyGraphviz      | Graph visualization tool is used to create a .dot-file representation of JET's computation graph |
| Graphviz        | Required by PyGraphviz |
| NetworkX        | JET's computation graph is stored using NetworkX. |
| ClangFormat     | Used to auto-format the C++ code |

***

## Internals

When you compile a graph, the first thing that happens is that all nodes that
lead to the specified outputs are collected. Then they are topologically sorted,
which makes sure that all operations appear in the correct order. One simple
optimization happens, which merges specific operations together to make use of
Armadillos lazy evaluation strategy.

Internally, pybind11 and cppimport are used to generate the C++ to Python glue.
