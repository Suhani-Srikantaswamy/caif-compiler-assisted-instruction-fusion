/* Small example for exploring how LLVM orders and pairs memory operations.
 * Two loads from the same 64-byte region (a[0], a[1]) are separated in the
 * source by unrelated work. */
long demo(const long *a, const long *b, long x, long y) {
    long v0 = a[0];          /* HEAD candidate */
    long t  = x * y + 7;     /* catalyst: independent arithmetic */
    long w  = b[3];          /* catalyst: load from another object */
    long v1 = a[1];          /* TAIL candidate: a+8 bytes */
    return v0 + v1 + t + w;
}
