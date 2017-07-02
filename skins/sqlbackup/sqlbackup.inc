## identifier for standard skin
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
## This version is for use with seasons/index.html.tmpl
## it comes with a few issues, see sqlbackupREADME.html

#errorCatcher Echo

<div id='sqlbackup_widget' class="widget">
  <div class="widget_title">
    <a class="widget_control_left"
      onclick="toggle_widget('sqlbackup')">&diams;</a>
    <a  href="sqlbackup/sqlbackup.html">SQLBackup</a>
    <a class="widget_control"
      onclick="toggle_widget('sqlbackup')">&diams;</a>
  </div>
  <div class="widget_contents">
  <table><tbody>
    <tr>
       <td class="label">
       &nbsp;Last run was on
        #include "/tmp/sqlbackup/head.inc"
     </td>
    </tr>
  </tbody></table>
  </div>
</div>
