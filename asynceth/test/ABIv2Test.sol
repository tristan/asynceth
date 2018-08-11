pragma solidity ^0.4.24;
pragma experimental ABIEncoderV2;

contract ABIv2Test {
  struct S { uint a; uint[] b; T[] c; }
  struct T { uint x; uint y; }
  struct U { uint [][] a; }

  function f(S memory s, T memory t, uint a) public { }
  function g() public view returns (S memory s, T memory t, uint a) {
    uint[] memory b = new uint[](2);
    b[0] = 2;
    b[1] = 3;
    T[] memory c = new T[](2);
    c[0] = T(4, 5);
    c[1] = T(6, 7);
    return (S(1, b, c), T(8, 9), 10);
  }

  function testStructArrayInput(T[] memory t) public view returns (uint) {
    uint rval = 0;
    for (uint i = 0; i < t.length; i++) {
      rval += t[i].x + t[i].y;
    }
    return rval;
  }

  function testStructMultidimensionalArrayOutput() public view returns (T[][2]) {
    T[] memory a = new T[](2);
    a[0] = T(1, 2);
    a[1] = T(3, 4);
    T[] memory b = new T[](2);
    b[0] = T(5, 6);
    b[1] = T(7, 8);
    T[][2] memory rval = [a, b];

    return rval;
  }

  function testArrayOutput() public view returns (uint[]) {
    uint[] memory a = new uint[](2);
    a[0] = 1;
    a[1] = 2;
    return a;
  }

  function testMultidimensionalArrayOutput() public view returns (uint[][]) {
    uint[] memory a = new uint[](2);
    a[0] = 1;
    a[1] = 2;
    uint[] memory b = new uint[](2);
    b[0] = 3;
    b[1] = 4;
    uint[][] memory rval = new uint[][](2);
    rval[0] = a;
    rval[1] = b;
    return rval;
  }

  function testMultidimensionalArrayInput(uint[][] t) public pure returns (uint) {
    uint rval = 0;
    for (uint i = 0; i < t.length; i++) {
      for (uint ii = 0; ii < t[i].length; ii++) {
        rval += t[i][ii];
      }
    }
    return rval;
  }

  function testStructWithMultidimensionalArrayOutput() public pure returns (U) {
    uint[] memory a = new uint[](2);
    a[0] = 1;
    a[1] = 2;
    uint[] memory b = new uint[](2);
    b[0] = 3;
    b[1] = 4;
    uint[][] memory rval = new uint[][](2);
    rval[0] = a;
    rval[1] = b;
    return U(rval);
  }

  function testStructWithMultidimensionalArrayInput(U u) public pure returns (uint) {
    uint rval = 0;
    for (uint i = 0; i < u.a.length; i++) {
      for (uint ii = 0; ii < u.a[i].length; ii++) {
        rval += u.a[i][ii];
      }
    }
    return rval;
  }
}
