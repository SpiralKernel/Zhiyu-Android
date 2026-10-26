package org.aiteacher.offline;

import android.app.Activity;
import android.content.*;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import android.webkit.*;
import android.widget.*;
import androidx.core.content.FileProvider;
import com.chaquo.python.Python;
import org.json.JSONObject;
import java.io.*;
import java.net.URL;
import java.net.HttpURLConnection;
import java.util.UUID;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private WebView web;
    private FrameLayout content;
    private String origin;
    private ValueCallback<Uri[]> filesCallback;
    private Uri captureUri;
    private File captureFile;
    private String downloadUrl;
    private final java.util.concurrent.ExecutorService worker=Executors.newSingleThreadExecutor();
    private static final int PICK_FILE=71,SAVE_FILE=72;

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        PdfSupport.context=getApplicationContext();
        getWindow().setStatusBarColor(Color.rgb(247,243,234));getWindow().setNavigationBarColor(Color.rgb(247,243,234));
        web=new WebView(this);web.setBackgroundColor(Color.rgb(247,243,234));
        content=new FrameLayout(this);content.setBackgroundColor(Color.rgb(247,243,234));
        content.addView(web,new FrameLayout.LayoutParams(-1,-1));
        content.setOnApplyWindowInsetsListener((view,insets)->{
            if(Build.VERSION.SDK_INT>=30){
                android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars());
                view.setPadding(bars.left,bars.top,bars.right,bars.bottom);
            }else view.setPadding(insets.getStableInsetLeft(),insets.getStableInsetTop(),insets.getStableInsetRight(),insets.getStableInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);settings.setSupportMultipleWindows(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.addJavascriptInterface(new ThemeBridge(),"AndroidTheme");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                String u=request.getUrl().toString();if(local(u))return false;
                if("https".equals(request.getUrl().getScheme()))try{startActivity(new Intent(Intent.ACTION_VIEW,request.getUrl()));}catch(ActivityNotFoundException ignored){}
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                String u=request.getUrl().toString();if(local(u)||u.startsWith("data:")||u.startsWith("blob:"))return null;
                return new WebResourceResponse("text/plain","UTF-8",403,"Forbidden",null,new ByteArrayInputStream(new byte[0]));
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(filesCallback!=null)filesCallback.onReceiveValue(null);filesCallback=callback;
                boolean multiple=params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE;
                boolean images=false,imagesOnly=params.getAcceptTypes().length>0;
                for(String type:params.getAcceptTypes()){
                    boolean image=type.startsWith("image/")||type.equals(".jpg")||type.equals(".jpeg")||type.equals(".png")||type.equals(".webp");
                    images|=image;imagesOnly&=image;
                }
                Intent files=new Intent(Intent.ACTION_OPEN_DOCUMENT);files.addCategory(Intent.CATEGORY_OPENABLE);
                files.setType(imagesOnly?"image/*":"*/*");files.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,multiple);
                Intent pick=files;
                if(imagesOnly){
                    Intent gallery=new Intent(Build.VERSION.SDK_INT>=33?MediaStore.ACTION_PICK_IMAGES:Intent.ACTION_GET_CONTENT);
                    gallery.setType("image/*");
                    if(multiple){if(Build.VERSION.SDK_INT>=33)gallery.putExtra(MediaStore.EXTRA_PICK_IMAGES_MAX,4);else gallery.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);}
                    if(gallery.resolveActivity(getPackageManager())!=null)pick=gallery;
                }
                Intent chooser=Intent.createChooser(pick,imagesOnly?"选择图片":"选择文件");captureUri=null;captureFile=null;
                java.util.ArrayList<Intent> alternatives=new java.util.ArrayList<>();
                if(pick!=files)alternatives.add(files);
                if(images){
                    File dir=new File(getCacheDir(),"camera");dir.mkdirs();captureFile=new File(dir,UUID.randomUUID()+".jpg");
                    captureUri=FileProvider.getUriForFile(MainActivity.this,getPackageName()+".files",captureFile);
                    Intent camera=new Intent(MediaStore.ACTION_IMAGE_CAPTURE);camera.putExtra(MediaStore.EXTRA_OUTPUT,captureUri);
                    camera.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                    if(camera.resolveActivity(getPackageManager())!=null)alternatives.add(camera);
                }
                if(!alternatives.isEmpty())chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS,alternatives.toArray(new Intent[0]));
                try{startActivityForResult(chooser,PICK_FILE);}catch(ActivityNotFoundException e){callback.onReceiveValue(null);filesCallback=null;}
                return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request){request.deny();}
        });
        web.setDownloadListener((url,agent,disposition,mime,size)->{
            if(!local(url))return;downloadUrl=url;
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType(mime==null?"application/octet-stream":mime);
            intent.putExtra(Intent.EXTRA_TITLE,URLUtil.guessFileName(url,disposition,mime));
            try{startActivityForResult(intent,SAVE_FILE);}catch(ActivityNotFoundException e){toast("未找到文件保存程序");}
        });
        showLoading();
        worker.execute(()->{
            try{
                File root=new File(getFilesDir(),"runtime");root.mkdirs();
                File stamp=new File(root,".assets-version");String version=Long.toString(getPackageManager().getPackageInfo(getPackageName(),0).lastUpdateTime);
                if(!stamp.exists()||!version.equals(read(stamp))){copyAssets("runtime",root);try(FileOutputStream out=new FileOutputStream(stamp)){out.write(version.getBytes("UTF-8"));}}
                JSONObject endpoint=new JSONObject(Python.getInstance().getModule("mobile_bootstrap").callAttr("start",root.getAbsolutePath()).toString());
                origin=endpoint.getString("url");String token=endpoint.getString("token");
                runOnUiThread(()->{
                    CookieManager.getInstance().setCookie(origin,"teacher_device_token="+token+"; Path=/; HttpOnly; SameSite=Strict",ok->{
                        CookieManager.getInstance().flush();setContentView(content);content.requestApplyInsets();web.loadUrl(origin+"/");
                    });
                });
            }catch(Exception e){android.util.Log.e("AI-teacher","Local startup failed",e);runOnUiThread(()->{
                LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(32,80,32,32);
                TextView message=new TextView(this);message.setText("本地启动未完成，请重新打开应用。学习记录仍保存在手机中。");box.addView(message);
                Button retry=new Button(this);retry.setText("重试");retry.setOnClickListener(v->recreate());box.addView(retry);setContentView(box);
            });}
        });
    }
    private boolean local(String url){
        if(origin==null)return false;
        try{Uri actual=Uri.parse(url),base=Uri.parse(origin);return base.getScheme().equals(actual.getScheme())&&base.getHost().equals(actual.getHost())&&base.getPort()==actual.getPort();}catch(Exception e){return false;}
    }
    private void showLoading(){
        LinearLayout box=new LinearLayout(this);box.setGravity(android.view.Gravity.CENTER);box.setOrientation(LinearLayout.VERTICAL);box.setBackgroundColor(Color.rgb(247,243,234));
        TextView title=new TextView(this);title.setText("知域");title.setTextColor(Color.rgb(64,54,46));title.setTextSize(26);box.addView(title);
        ProgressBar progress=new ProgressBar(this);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(56,56);p.topMargin=30;box.addView(progress,p);
        TextView subtitle=new TextView(this);subtitle.setText(new File(getFilesDir(),"runtime/data/ai-teacher.sqlite3").exists()?"正在打开题库":"首次启动正在准备离线题库");subtitle.setTextColor(Color.rgb(121,108,96));p=new LinearLayout.LayoutParams(-2,-2);p.topMargin=24;box.addView(subtitle,p);setContentView(box);
    }
    private void copyAssets(String path,File destination)throws IOException{
        String[] names=getAssets().list(path);
        if(names!=null&&names.length>0){destination.mkdirs();for(String child:names)copyAssets(path+"/"+child,new File(destination,child));}
        else{destination.getParentFile().mkdirs();File part=new File(destination.getPath()+".part");try(InputStream in=getAssets().open(path);OutputStream out=new FileOutputStream(part)){byte[] b=new byte[65536];for(int n;(n=in.read(b))>0;)out.write(b,0,n);}if(!part.renameTo(destination))throw new IOException("Cannot install assets");}
    }
    private String read(File file)throws IOException{try(InputStream in=new FileInputStream(file)){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[1024];for(int n;(n=in.read(b))>0;)out.write(b,0,n);return out.toString("UTF-8");}}
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request==PICK_FILE&&filesCallback!=null){
            Uri[] selected=null;
            if(result==RESULT_OK){
                if(data!=null&&data.getClipData()!=null){ClipData clip=data.getClipData();selected=new Uri[clip.getItemCount()];for(int i=0;i<selected.length;i++)selected[i]=clip.getItemAt(i).getUri();}
                else if(data!=null&&data.getData()!=null)selected=new Uri[]{data.getData()};
                else if(captureFile!=null&&captureFile.length()>0)selected=new Uri[]{captureUri};
            }
            filesCallback.onReceiveValue(selected);filesCallback=null;
        }else if(request==SAVE_FILE&&result==RESULT_OK&&data!=null&&data.getData()!=null){
            final Uri target=data.getData();final String url=downloadUrl;final String cookie=CookieManager.getInstance().getCookie(url);
            worker.execute(()->{try{
                if(!local(url))throw new IOException();HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setInstanceFollowRedirects(false);c.setRequestProperty("Cookie",cookie==null?"":cookie);c.setConnectTimeout(15000);c.setReadTimeout(60000);
                try{if(c.getResponseCode()!=200)throw new IOException();try(InputStream in=c.getInputStream();OutputStream out=getContentResolver().openOutputStream(target)){byte[] b=new byte[65536];for(int n;(n=in.read(b))>0;)out.write(b,0,n);}}finally{c.disconnect();}toast("已保存");
            }catch(Exception e){toast("保存失败，请重试");}});
        }
    }
    private void toast(String text){runOnUiThread(()->Toast.makeText(this,text,Toast.LENGTH_SHORT).show());}
    @Override public void onBackPressed(){
        web.evaluateJavascript("(()=>{let b=document.querySelector('.dialog-shade button')||document.querySelector('.writing-wide button[aria-label=\"展开 / 收起大答题纸\"]');if(b){b.click();return true;}return false;})()",result->{if(!"true".equals(result)){if(web.canGoBack())web.goBack();else MainActivity.super.onBackPressed();}});
    }
    public final class ThemeBridge {
        @JavascriptInterface public void apply(String color,boolean dark){
            if(!color.matches("#[0-9a-fA-F]{6}"))return;
            runOnUiThread(()->{int value=Color.parseColor(color);web.setBackgroundColor(value);content.setBackgroundColor(value);getWindow().setStatusBarColor(value);getWindow().setNavigationBarColor(value);
                int flags=web.getSystemUiVisibility();if(dark)flags&=~android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;else flags|=android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;web.setSystemUiVisibility(flags);});
        }
    }
}
