package com.ped3.chat.shared.util;

public class CaesarCipher {

    // Desplazamiento sobre el rango de caracteres imprimibles ASCII (32–126)
    private static final int SHIFT = 47;
    private static final int PRINTABLE_START = 32;
    private static final int PRINTABLE_RANGE = 95; // 126 - 32 + 1

    public static String encrypt(String text) {
        StringBuilder sb = new StringBuilder(text.length());
        for (char c : text.toCharArray()) {
            if (c >= PRINTABLE_START && c <= 126) {
                sb.append((char) (PRINTABLE_START + (c - PRINTABLE_START + SHIFT) % PRINTABLE_RANGE));
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    public static boolean matches(String plain, String encrypted) {
        return encrypt(plain).equals(encrypted);
    }
}
