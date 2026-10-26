package org.aiteacher.offline;
import android.util.Base64;
import java.security.*;
import java.security.spec.X509EncodedKeySpec;
public final class UpdateVerifier {
    public static boolean verify(String data,String signature,String pem) throws Exception {
        String text=pem.replace("-----BEGIN PUBLIC KEY-----","").replace("-----END PUBLIC KEY-----","").replaceAll("\\s","");
        PublicKey key=KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Base64.decode(text,Base64.DEFAULT)));
        Signature verifier=Signature.getInstance("SHA256withRSA");verifier.initVerify(key);verifier.update(Base64.decode(data,Base64.DEFAULT));
        return verifier.verify(Base64.decode(signature,Base64.DEFAULT));
    }
}
