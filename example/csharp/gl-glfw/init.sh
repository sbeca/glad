#!/bin/sh

BASE_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

cd "${BASE_PATH}/../../../"

python -m glad --out-path "${BASE_PATH}/build" --extensions="" --api="gl:core=3.3" csharp
