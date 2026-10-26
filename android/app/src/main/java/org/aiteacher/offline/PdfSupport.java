package org.aiteacher.offline;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Canvas;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import android.util.Base64;
import org.json.JSONArray;
import java.io.*;
public final class PdfSupport {
    public static Context context;
    public static String render(String data,int first,int last) throws Exception {
        if(first<1||last<first||last-first>=8)throw new IllegalArgumentException();
        File file=File.createTempFile("pdf-",".pdf",context.getCacheDir());
        try {
            try(FileOutputStream out=new FileOutputStream(file)){out.write(Base64.decode(data,Base64.DEFAULT));}
            JSONArray result=new JSONArray();
            try(ParcelFileDescriptor fd=ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);PdfRenderer renderer=new PdfRenderer(fd)){
                if(last>renderer.getPageCount())throw new IllegalArgumentException();
                for(int i=first-1;i<last;i++)try(PdfRenderer.Page page=renderer.openPage(i)){
                    float scale=1800f/Math.max(page.getWidth(),page.getHeight());
                    Bitmap b=Bitmap.createBitmap(Math.max(1,(int)(page.getWidth()*scale)),Math.max(1,(int)(page.getHeight()*scale)),Bitmap.Config.ARGB_8888);
                    new Canvas(b).drawColor(Color.WHITE);page.render(b,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                    ByteArrayOutputStream out=new ByteArrayOutputStream();b.compress(Bitmap.CompressFormat.PNG,100,out);b.recycle();
                    result.put(Base64.encodeToString(out.toByteArray(),Base64.NO_WRAP));
                }
            }
            return result.toString();
        }finally{file.delete();}
    }
}
