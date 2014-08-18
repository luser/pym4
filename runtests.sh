#!/bin/bash

for t in `dirname $0`/test/*.in; do
  tmp=`mktemp m4test.XXXXXXXXXX`
  expected=${t/.in/.out}
  m4 $t > $tmp
  if diff $expected $tmp; then
      rm $tmp
  else
      echo "Error in $t"

  fi
done
